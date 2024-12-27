import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging import getLogger
from urllib.parse import urlparse, parse_qs

from astropy.wcs import WCS

from dk154_control.utils import dec_dms_to_deg, ra_hms_to_deg

from dk154_mock.hardware import MockDk154
from dk154_mock.hardware import MockCcd3

logger = getLogger("MockCCD3Server")

ccd3_to_ascol_shutter = {"0": "1", "1": "0"}


class MockCcd3Server(ThreadingHTTPServer):

    def __init__(
        self,
        obs: MockDk154,
        server_address,
        RequestHandlerClass: type,
    ):
        self.server_address = server_address

        msg = (
            f"init MockCCD3Server with:\n    handler={RequestHandlerClass.__name__} "
            f"at {server_address[0]}:{server_address[1]}"
        )
        logger.info(msg)
        self.obs = obs

        super().__init__(server_address, RequestHandlerClass)


FLOAT_PARAMETERS = ["CCD3.exposure"]


class Ccd3RequestHandler(BaseHTTPRequestHandler):

    def __init__(self, request, client_address, server: MockCcd3Server):

        super().__init__(request, client_address, server)

        self.client_address = client_address
        self.server: MockCcd3Server  # Update type hint.

    def do_GET(self):

        logger.debug(f"process GET:\n    path={self.path}")
        parsed_input = urlparse(url=self.path, scheme="http")
        path_cmd = parsed_input.path
        if not path_cmd.startswith("/api"):
            msg = r"CCD3 query should start with '/api/<cmd-here>'!"
            logger.error(msg)
            self.send_error(400, message=f"Unknown {path_cmd}", explain=msg)
            self.end_headers()
            return

        parsed_parameters = parse_qs(parsed_input.query, keep_blank_values=True)
        parameters = {}
        for k, v in parsed_parameters.items():
            if len(v) < 2:
                param_ii = v[0]
            else:
                param_ii = v
            if k in FLOAT_PARAMETERS:
                param_ii = float(param_ii)
            parameters[k] = param_ii

        cmd = path_cmd.split("/")[-1]

        response_code = 200  # assume everything will be fine
        if cmd == "get":
            data = {"state": self.server.obs.ccd3.get_ccd_state()}
        elif cmd == "mset":
            self.server.obs.ccd3.set_exposure_parameters(parameters)
            data = {"state": self.server.obs.ccd3.get_ccd_state()}
        elif cmd == "expose":

            shutter_param = self.server.obs.ccd3.ccd_parameters.get(
                "CCD3.SHUTTER", None
            )
            if shutter_param is None:
                shutter_param = "0"
                msg = "NO 'CCD3.SHUTTER' param: defaults to '0'='open' (opposite of ASCOL!)"
                logger.warning(msg)
            if shutter_param not in ["0", "1"]:
                msg = f"shutter parameter must be in ['0', '1'] ('0'='open', '1'='closed')"
                logger.error(msg)
                self.send_error(
                    400, message=f"Unknown shutter param {shutter_param}", explain=msg
                )
                self.end_headers()
                return
            ascol_shutter_param = ccd3_to_ascol_shutter[shutter_param]
            self.server.obs.telescope.set_shutter_pos(ascol_shutter_param)

            filepath = parameters.get("fe", None)
            if filepath is None:
                msg = f"must provide 'fe' parameter, filepath for imgout"
                logger.error(msg)
                self.send_error(400, message=f"Missing param 'fe'", explain=msg)
                self.end_headers()
                return

            ccd_param = parameters.get("ccd", None)
            if ccd_param != "CCD3":
                msg = f"must provide parameter ccd='ccd3'"
                logger.error(msg)
                self.send_error(400, message=f"Missing param 'ccd'", explain=msg)
                self.end_headers()

            header = self.create_output_header()
            self.server.obs.ccd3.take_exposure(filepath, header=header)
            data = {"state": self.server.obs.ccd3.get_ccd_state()}
        else:
            msg = f"Unknown command {path_cmd}"
            logger.error(msg)
            self.send_error(400, message=f"Unknown {path_cmd}", explain=msg)
            self.end_headers()
            return

        logger.debug("processed data, send return")
        self.send_response(response_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def create_output_header(self):

        t_ref = self.server.obs.telescope.get_t_ref()
        ra, dec, pos = self.server.obs.telescope.get_telescope_position()
        shutter_pos = self.server.obs.telescope.get_shutter_pos()
        filter_a = self.server.obs.telescope.get_wheel_a_pos()
        filter_b = self.server.obs.telescope.get_wheel_b_pos()

        exptime = self.server.obs.ccd3.loaded_parameters.get("CCD3.exposure", None)
        object_name = self.server.obs.ccd3.loaded_parameters.get("CCD3.OBJECT", None)
        img_type = self.server.obs.ccd3.loaded_parameters.get("CCD3.IMAGETYP", None)
        binning = self.server.obs.ccd3.loaded_parameters.get("CCD3.binning", "1x1")

        if object_name is None:
            logger.warning("failed to add CCD3.OBJECT")
        if img_type is None:
            logger.warning("failed to set CCD3.IMAGETYP")

        gain = self.server.obs.ccd3.ccd_parameters["gain"]
        pix_size = self.server.obs.ccd3.ccd_parameters["pix_size"]
        plate_scale = self.server.obs.ccd3.ccd_parameters["plate_scale"]
        ylen, xlen = self.server.obs.ccd3.get_output_image_shape()  # factor in binning
        yscale, xscale = self.server.obs.ccd3.get_output_image_plate_scale()  # binning

        w = WCS(naxis=2)
        w.wcs.crpix = [ylen / 2, xlen / 2]
        w.wcs.cdelt = [yscale / 3600.0, xscale / 3600.0]
        w.wcs.crval = [ra, dec]
        w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
        w.wcs.set_pv([(2, 1, 45.0)])

        header = w.to_header()

        header_data = {
            "JD": (t_ref.jd, "exposure JD"),
            "DATE-OBS": (t_ref.isot, "Start of exposure"),
            "OBJECT": (object_name, "object name"),
            "OBSERVAT": ("Mock La Silla", "This is a MOCK observation"),
            "TELESCOP": ("DK-1.54 MOCK", "telescope - This is a MOCK observation"),
            "EXPTIME": (exptime, "exposure time in sec"),
            "GAIN1": (gain, "Channel 1 gain [copied from a real CCD3 fits!]"),
            "GAIN2": (gain, "Channel 2 gain [copied from a real CCD3 fits!]"),
            "SECPPIX": (plate_scale, "Arcseconds per pixel"),
            "CCDPSIZ": (pix_size, "pre-binning "),
            "IMAGETYP": (img_type, "type of frame"),
            "SHUTTER": (shutter_pos, "shutter position (0 - opened, 1 - closed)"),
            "FILTA": (filter_a, "FASU A filter"),
            "FILTB": (filter_b, "FASU B filter"),
        }

        header.update(header_data)
        return header


def get_mock_ccd3_server(mock_dk154, port=8884) -> MockCcd3Server:
    return MockCcd3Server(mock_dk154, ("localhost", port), Ccd3RequestHandler)


if __name__ == "__main__":

    dk154 = MockDk154.start_ready()

    ccd3_response_server = get_mock_ccd3_server(dk154)
    ccd3_response_server.serve_forever()
