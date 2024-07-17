import time
from logging import getLogger
from pathlib import Path

import numpy as np

from astropy import units as u
from astropy.coordinates import SkyCoord, ICRS
from astropy.io import fits
from astropy.modeling.models import Gaussian2D, Moffat2D2D
from astropy.wcs import WCS

try:
    from astropy_healpix import HEALPix
except ImportError as e:
    HEALPix = None

from dk154_control import utils

from dk154_mock import paths

logger = getLogger("MockCCD3")

noise_rng = np.random.default_rng(1234)

CAMERA_READY = 0  # TODO: check this is true!
CAMERA_READING = 2
CAMERA_HAS_IMAGE = 8
DEVICE_ERROR_KILL = 65536
CAMERA_EXPOSING_SHUTTER_OPEN = 67108865

EXPECTED_PARAMETERS = (
    "async",
    "CCD3.exposure",
    "CCD3.IMAGETYP",
    "CCD3.OBJECT",
    "WASA.filter",
    "WASB.filter",
)


def image_to_hdu(image, header=None):

    return fits.PrimaryHDU(data=image, header=header)


def _parse_binning(binning: str):
    ystr, xstr = binning.split("x")
    return int(ystr), int(xstr)


def gen_bias(im: np.ndarray, value: int, bad_columns: int = 0):
    bias_im = im + value

    if bad_columns > 0:
        col_rng = np.random.default_rng(1234)
        columns = col_rng.integers(0, im.shape[1], size=bad_columns)
        col_pattern = col_rng.integers(0, int(0.1 * value), size=im.shape[0])

        for col in columns:
            bias_im[:, col] = bias_im[:, col] + col_pattern
    return bias_im


def gen_dark(
    im: np.ndarray, current: float, exptime: float, gain: float, hot_pix: float = 0
):
    base_current = current * exptime / gain

    dark_im = noise_rng.poisson(base_current, size=im.shape)

    if hot_pix > 0:
        pix_rng = np.random.default_rng(54321)

        y_max, x_max = im.shape
        n_hot = int(hot_pix * x_max * y_max)

        hot_x = pix_rng.integers(0, x_max, size=n_hot)
        hot_y = pix_rng.integers(0, y_max, size=n_hot)

        dark_im[(hot_y, hot_x)] = 10000 * current * exptime / gain

    return dark_im


def gen_sky_noise(im: np.ndarray, sky_counts: float, gain: float, overscan: int = 0):

    sky_rng = np.random.default_rng()
    sky_im = np.zeros(im.shape)

    noise_shape = np.array([[im.shape[0], im.shape[1] - overscan]])
    sky_noise = sky_rng.poisson(sky_counts * gain, size=noise_shape) / gain

    sky_im[:, :-overscan] = sky_noise
    return sky_im


def gen_flat(im: np.ndarray, vignette=True):
    sensitivity = np.ones(im.shape)

    y, x = np.indices(im.shape)
    if vignette:
        vign_model = Gaussian2D(
            amplitude=1,
            x_mean=im.shape[0] / 2,
            y_mean=im.shape[1] / 2,
            x_stddev=2 * max(im.shape),
            y_stddev=2 * max(im.shape),
        )
        sensitivity = sensitivity * vign_model(x, y)
    return sensitivity


def gen_science(
    im: np.ndarray,
    header: fits.Header,
    exptime: float,
    seeing: float = 10.0,  # * u.arcsec,
    gain: float = 1.0,
    healpix_level: int = 11,
):
    if HEALPix is None:
        return np.zeros(im.shape)

    nside = 2**healpix_level
    hp = HEALPix(nside=nside, frame=ICRS())

    wcs = WCS(header)

    yc, xc = (im.shape[0] / 2, im.shape[1] / 2)

    im_centre_coord = SkyCoord.from_pixel(im.shape[1] / 2, im.shape[0] / 2, wcs)
    radius = 20 * u.arcmin

    near_hpix = hp.cone_search_skycoord(im_centre_coord, radius=radius)
    star_coords = hp.healpix_to_skycoord(near_hpix)

    x_impix, y_impix = star_coords.to_pixel(wcs)

    ymask = (0 < y_impix) & (y_impix < im.shape[0])
    xmask = (0 < x_impix) & (x_impix < im.shape[1])

    rel_hpix = near_hpix[xmask & ymask]
    rel_star_coords = star_coords[xmask & ymask]
    rel_y_impix = y_impix[xmask & ymask].round().astype(int)
    rel_x_impix = x_impix[xmask & ymask].round().astype(int)

    science_im = np.zeros(im.shape)

    for x_ii, y_ii, h_ii in zip(rel_x_impix, rel_y_impix, rel_hpix):

        size = h_ii % 4 + 2

        mag = h_ii % 7 + 12
        flux = 10 ** (-0.4 * (mag - 8.9)) * 10**6

        counts = flux * exptime / gain

        # is_star = h_ii % 3

        amp = counts / (2 * np.pi * (seeing / 2) ** 2)
        obj_model = Gaussian2D(
            amplitude=amp,
            x_mean=x_ii,
            y_mean=y_ii,
            x_stddev=seeing / 2.0,
            y_stddev=seeing / 2.0,
        )

        obj_model.render(science_im)

        ysl = slice(max(y_ii - size, 0), min(y_ii + size, im.shape[0] - 1))
        xsl = slice(max(x_ii - size, 0), min(x_ii + size, im.shape[1] - 1))

    return science_im


DEFAULT_CCD3_PARAMETERS = {
    "gain": 1.0,
    "bias_value": 1200.0,
    "ccd_xlen": 2148,
    "ccdy_len": 2064,
    "current": 0.1,
    "bad_columns": 8,
    "hot_pix": 0.0001,
    "sky_counts": 4,
    "overscan": 100,
    "plate_scale": 0.396,
    "pix_size": 0.0135,
}


class MockCcd3:

    READ_TIME = 30.0

    def __init__(self, data_path: Path = None, write_mock_data=True, effects=None):

        self.data_path = data_path or paths.base_path / "MOCK_DATA"
        self.write_mock_data = write_mock_data

        self._ccd_state = 0

        self._exposure_starttime = 0.0

        self.loaded_parameters = {}

        self.exposure_started = False

        self.ccd_parameters = DEFAULT_CCD3_PARAMETERS

    def updates_ccd_parameters(self, parameters):
        self.ccd_parameters.update(parameters)

    def get_ccd_state(self):
        self.set_ccd_state()
        return self._ccd_state

    def set_ccd_state(self):
        exptime = self.loaded_parameters.get("CCD3.exposure", None)

        if exptime is not None and self.exposure_started:
            total_image_time = float(exptime) + self.READ_TIME
            dt = time.time() - self._exposure_starttime
            if dt < total_image_time:
                if dt < exptime:
                    self._ccd_state = CAMERA_EXPOSING_SHUTTER_OPEN
                else:
                    self._ccd_state = CAMERA_READING
                return

            else:
                self.exposure_started = False
                for key in EXPECTED_PARAMETERS:
                    _ = self.loaded_parameters.pop(key, None)
                self._ccd_state = 0
                return
        else:
            return

    def set_exposure_parameters(self, parameters: dict):
        unexpected_parameters = [
            k for k in parameters.keys() if k not in EXPECTED_PARAMETERS
        ]
        if len(unexpected_parameters) > 0:
            msg = f"unexpected parameters:\n    {unexpected_parameters}"
            logger.error(msg)
            raise ValueError(msg)
        self.loaded_parameters.update(parameters)
        return

    def take_exposure(self, filepath: Path, shutter_open=True, header=None):
        self.data_path.mkdir(exist_ok=True)

        filepath = Path(filepath)
        if filepath.suffix not in [".fits", ".fit"]:
            print(filepath.suffix)
            msg = "filepath must end in '.fits' or '.fit' !"
            logger.warning(f"filepath {filepath} should end in '.fits' or '.fit'!")

        if "CCD3.exposure" not in self.loaded_parameters:
            msg = "no parameters set!"
            logger.error(msg)

        imgtype = self.loaded_parameters.get("CCD3.IMAGETYP", None)
        self.exposure_started = True

        if self.write_mock_data:

            blank = self.gen_blank_image()

            bias = gen_bias(
                blank,
                self.ccd_parameters["bias_value"],
                bad_columns=self.ccd_parameters["bad_columns"],
            )

            dark = gen_dark(
                blank,
                current=self.ccd_parameters["current"],
                exptime=self.loaded_parameters["CCD3.exposure"],
                gain=self.ccd_parameters["gain"],
                hot_pix=self.ccd_parameters["hot_pix"],
            )

            if shutter_open:
                flat = gen_flat(blank)
                sky = gen_sky_noise(
                    blank,
                    self.ccd_parameters["sky_counts"],
                    self.ccd_parameters["bias_value"],
                    self.ccd_parameters["overscan"],
                )

                science = gen_science(
                    blank, header, self.loaded_parameters["CCD3.exposure"]
                )
                image = bias + dark + flat * (sky + science)

            else:
                image = bias + dark

            hdu = image_to_hdu(image, header=header)

            filepath = self.data_path / filepath
            logger.info(f"writing image to:\n    {filepath}")
            hdu.writeto(filepath, overwrite=True)

    def get_output_image_shape(self):
        binning = self.loaded_parameters.get("CCD3.binning", "1x1")
        xbin, ybin = _parse_binning(binning)
        ccd_xlen = self.ccd_parameters.get("ccd_xlen", 2048)
        ccd_ylen = self.ccd_parameters.get("ccd_ylen", 2048)
        return int(ccd_ylen / ybin), int(ccd_xlen / xbin)

    def get_output_image_plate_scale(self):
        binning = self.loaded_parameters.get("CCD3.binning", "1x1")
        xbin, ybin = _parse_binning(binning)
        plate_scale = self.ccd_parameters.get("plate_scale", 0.4)
        return plate_scale * ybin, plate_scale * xbin

    def gen_blank_image(self):
        im_shape = self.get_output_image_shape()
        return np.zeros(im_shape)
