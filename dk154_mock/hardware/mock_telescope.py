import time
from logging import getLogger

import numpy as np

from astropy import units as u
from astropy.coordinates import SkyCoord, EarthLocation, AltAz, ICRS
from astropy.time import Time, TimeDelta

logger = getLogger("MockTelescope")


def get_waypoint_formula(c1: SkyCoord, c2: SkyCoord):
    d = c1.separation(c2)

    def waypoint_formula(f):
        # https://edwilliams.org/avform147.htm

        A = np.sin((1 - f) * d) / np.sin(d)
        B = np.sin(f * d) / np.sin(d)

        x = A * np.cos(c1.dec) * np.cos(c1.ra) + B * np.cos(c2.dec) * np.cos(c2.ra)
        y = A * np.cos(c1.dec) * np.sin(c1.ra) + B * np.cos(c2.dec) * np.sin(c2.ra)
        z = A * np.sin(c1.dec) + B * np.sin(c2.dec)
        r = np.sqrt(x * x + y * y)

        lat = np.arctan2(z, r)
        lon = np.arctan2(y, x)
        return lon, lat


icrs = ICRS()


class MockTelescope:

    LOGIN_TIMEOUT = 120.0
    SLEW_TIME = 10.0
    SLEW_RATE = 1.0  # deg/sec.
    WHEEL_TIME = 20.0
    FLAP_TIME = 8.0
    SKY_FLIP_TIME = 10.0

    DOME_SLIT_TIME = 8.0
    DOME_PARK_TIME = 10.0
    DOME_INIT_TIME = 10.0
    DOME_MOVE_RATE = 0.2  # deg / sec
    DOME_PARKED_POSITION = 10.0
    MAX_AUTO_DOME_OFFSET = 5.0

    FOCUS_TIME = 3.0
    FOCUS_RATE = 1  # mm / sec
    FOCUS_MIN_POS = -50.0
    FOCUS_MAX_POS = 50.0

    def __init__(self, t_start: Time = None):

        self.t_start = t_start or Time.now()  # "Fake time"
        self.t_init = time.time()  # To count 'real' time since telescope started.

        self._location = EarthLocation.of_site("lasilla")
        self._obs_lat = self._location.lat  # -29.2567 * u.deg
        self._obs_lon = self._location.lon  # -70.73 * u.deg
        self._obs_height = self._location.height  # 2347.0 * u.m

        self._remote_state = "0"
        self._safety_relay_state = "0"
        self._tel_state = "05"
        self._dome_state = "00"
        self._dome_position = self.DOME_PARKED_POSITION
        self._dome_slit_state = "04"
        self._shutter_pos = "0"

        self._wheel_a_pos = "0"
        self._wheel_a_state = "04"
        self._wheel_a_starttime = 0.0  # Timer
        self._wheel_b_moving = False
        self._wheel_b_pos = "3"
        self._wheel_b_state = "04"
        self._wheel_b_starttime = 0.0  # Timer
        self._wheel_b_moving = False

        self._az = 1.0
        self._alt = 89.0
        self._altaz = AltAz(
            az=self._az * u.deg,
            alt=self._alt * u.deg,
            obstime=self.t_start,
            location=self._location,
        )
        self.update_radec_from_altaz()  # sets self._ra, self._dec
        self._slew_waypoint_formula = None

        self._tel_pos = "0"
        self._tel_on = True
        self._tel_stopped = True
        self._tel_slewing = False
        self._tel_flipping = False
        self._tel_parking = False
        self._slew_starttime = 0.0
        self._flip_starttime = 0.0

        self._logged_in = False
        self._login_time = 0.0

        self._dome_initalized = False
        self._dome_auto = False
        self._dome_moving = False
        self._dome_parking = False
        self._dome_stopped = True
        self.dome_move_time = None
        self._dome_init_starttime = 0.0
        self._dome_move_starttime = 0.0
        self._dome_slit_starttime = 0.0

        self._flap_cassegrain_state = "04"
        self._flap_cassegrain_starttime = 0.0
        self._flap_mirror_state = "04"
        self._flap_mirror_starttime = 0.0

        self._focus_pos = 0.0
        self._focus_state = "00"
        self._focus_starttime = 0.0

        self._pre_slew_coord = None

        self.loaded_parameters = {}

    @classmethod
    def start_in_ready_state(cls):
        telescope = cls()
        telescope._tel_state = "04"
        return telescope

    def update_login_status(self):
        dt = time.time() - self._login_time
        logger.info(f"logged in {dt:.2f} sec ago")
        if dt < self.LOGIN_TIMEOUT:
            self._logged_in = True
        else:
            self._logged_in = False
        return

    def get_login_status(self):
        self.update_login_status()
        return self._logged_in

    def get_t_ref(self):
        return self.t_start + TimeDelta(time.time() - self.t_init, format="sec")

    def update_radec_from_altaz(self):
        t_ref = self.get_t_ref()

        self._skycoord: SkyCoord = self._altaz.transform_to(icrs)
        self._ra = self._skycoord.ra.deg
        self._dec = self._skycoord.dec.deg

    def update_altaz_from_radec(self):
        t_ref = self.get_t_ref()

        self._altaz: AltAz = self._skycoord.transform_to(
            AltAz(obstime=t_ref, location=self._location)
        )
        self._alt = self._altaz.alt.deg
        self._az = self._altaz.az.deg

    def set_telescope_position(self, ra, dec, tel_pos):
        self.loaded_parameters["ra"] = ra
        self.loaded_parameters["dec"] = dec
        self.loaded_parameters["tel_pos"] = tel_pos
        print(self.loaded_parameters)

        if tel_pos not in ["0", "1"]:
            raise ValueError(f"Unknown telescope position: {tel_pos}. Use '0' or '1'!")

    def go_telescope_radec(self):
        ra = self.loaded_parameters.pop("ra", None)
        dec = self.loaded_parameters.pop("dec", None)
        tel_pos = self.loaded_parameters.pop("tel_pos", None)
        if any([x is None for x in [ra, dec, tel_pos]]):
            msg = f"One of ra={ra}, dec={dec}, pos={tel_pos} not set. Use TSRA!"
            raise ValueError(msg)

        new_skycoord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg)
        self._slew_waypoint_formula = get_waypoint_formula(self._skycoord, new_skycoord)

        slew_angle = self._skycoord.separation(new_skycoord)
        self.slew_time = slew_angle.deg / self.SLEW_RATE

        self._tel_stopped = False
        if tel_pos == self._tel_pos:
            # No flip required
            self._tel_slewing = True
            self._slew_starttime = time.time()
        else:
            self._tel_slewing = False  # not yet... start slew after flip finished.
            self._slew_startime = time.time() + self.FLIP_TIME
            self.telescope_skyflip(tel_pos)
        return

    def telescope_skyflip(self, new_pos):
        self._flip_starttime = time.time()
        self._tel_flip = True
        self.loaded_parameters["tel_pos"] = new_pos

    def telescope_stop(self):
        self._tel_stopped = True
        self._update_telescope_state()

    def get_telescope_position(self):
        self._update_telescope_state()
        logger.debug(f"get tel position: {self._ra} {self._dec} {self._tel_pos}")
        return self._ra, self._dec, self._tel_pos

    def _update_telescope_state(self):
        t_now = time.time()

        if self._tel_stopped:
            if self._tel_on:
                self._tel_state = "04"  # ready
            else:
                self._tel_state = "00"  # switched off
        else:
            if self._tel_flipping:
                if t_now - self._flip_starttime < self.SKY_FLIP_TIME:
                    self._tel_state = "09"  # skyflip
                else:
                    self._tel_flipping = False
                    if t_now - self._slew_starttime < self.slew_time:
                        self._tel_slewing = True
            if self._tel_slewing:
                dt = t_now - self._slew_starttime
                f = dt / self.slew_time  # fraction of way through slew.
                if f < 0:
                    raise ValueError("something went wrong: {f} <0")
                if f < 1:
                    if self._slew_waypoint_formula is None:
                        raise ValueError("slew waypoint formula not set correctly")
                    inter_ra, inter_dec = self._slew_waypoint_formula(f)
                    self._ra = inter_ra
                    self._dec = inter_dec
                    if self._tel_parking:
                        self._tel_state = "10"  # parking
                    else:
                        self._tel_state = "07"  # sky slew
                else:
                    ra = self.loaded_parameters.pop("ra")
                    dec = self.loaded_parameters.pop("dec")
                    tel_pos = self.loaded_parameters.pop("tel_pos")
                    self._ra = ra
                    self._dec = dec
                    self._tel_pos = tel_pos

                    self._tel_slewing = False
                    if self._tel_parking:
                        self._tel_parking = False
                        self._tel_on = False
                        self._tel_stopped = True
                        self._tel_state = "00"  # switched off
                    else:
                        self._tel_state = "05"  # sky track
            else:
                self._tel_state = "05"

        if self._tel_stopped:
            # Have constant altaz, sky rotates around stationary telescope
            self.update_radec_from_altaz()
        else:
            # Point at constant radec, by moving telescope altaz.
            self.update_altaz_from_radec()

        return

    def get_telescope_state(self):
        self._update_telescope_state()
        return self._tel_state

    def go_wheel_a(self):
        wheel_a_pos = self.loaded_parameters.pop("wheel_a_pos", None)
        if wheel_a_pos is None:
            msg = f"wheel_b_pos not set! use WASP first."
            logger.error(msg)
            raise ValueError(msg)
        self._wheel_a_starttime = time.time()
        self._wheel_a_pos = wheel_a_pos

    def _update_wheel_a_state(self):
        """Check if the wheel should be moving, or locked/ready, set the state accordingly"""
        if time.time() - self._wheel_a_starttime < self.WHEEL_TIME:
            self._wheel_a_state = "03"  # positioning
        else:
            self._wheel_a_state = "04"  # locked
        logger.debug(f"set _wheel_a_state {self._wheel_a_state}")

    def get_wheel_a_state(self) -> str:
        self._update_wheel_a_state()
        return self._wheel_a_state

    def set_wheel_a_pos(self, wheel_a_pos):
        """Load the position into the system, but not actually move there"""
        self.loaded_parameters["wheel_a_pos"] = wheel_a_pos
        return

    def get_wheel_a_pos(self) -> str:
        self._update_wheel_a_state()
        if self._wheel_a_state != "04":
            return "8"  # rotating
        return self._wheel_a_pos

    def go_wheel_b(self):
        wheel_b_pos = self.loaded_parameters.pop("wheel_b_pos", None)
        if wheel_b_pos is None:
            msg = f"wheel_b_pos not set! use WBSP first."
            raise ValueError(msg)
        self._wheel_b_starttime = time.time()
        self._wheel_b_pos = wheel_b_pos
        return

    def set_wheel_b_state(self):
        """Check if the wheel is moving, or stopped/ready, set the state accordingly"""
        if time.time() - self._wheel_b_starttime < self.WHEEL_TIME:
            self._wheel_b_state = "03"  # positioning
        else:
            self._wheel_b_state = "04"  # locked
        logger.debug(f"set _wheel_b_state {self._wheel_b_state}")
        return

    def get_wheel_b_state(self) -> str:
        self.set_wheel_b_state()
        return self._wheel_b_state

    def set_wheel_b_pos(self, wheel_b_pos):
        """Load the position into the system, but not actually move there"""
        self.loaded_parameters["wheel_b_pos"] = wheel_b_pos
        return

    def get_wheel_b_pos(self) -> str:
        self.set_wheel_b_state()
        if self._wheel_b_state != "04":  # locked
            return "7"  # rotating
        return self._wheel_b_pos

    def _update_flap_cassegrain_state(self):
        param = self.loaded_parameters.get("cassegrain_flap", None)
        if param is not None:
            if param == "stop":
                self._flap_cassegrain_state = "00"  # stopped
                _ = self.loaded_parameters.pop("cassegrain_flap")
                return
            elif param in ["open", "1"]:
                if time.time() - self._flap_cassegrain_starttime < self.FLAP_TIME:
                    self._flap_cassegrain_state = "01"  # opening
                    logger.debug("set cassegrain flap to OPENING [01]")
                    return
                else:
                    self._flap_cassegrain_state = "03"
                    # Remove the parameter, as opening has finished:
                    _ = self.loaded_parameters.pop("cassegrain_flap", None)
                    logger.debug("set cassegrain flap to OPEN [03]")
                    return
            elif param in ["close", "0"]:
                if time.time() - self._flap_cassegrain_starttime < self.FLAP_TIME:
                    self._flap_cassegrain_state = "02"
                    logger.debug("set cassegrain flap to CLOSING [02]")
                    return
                else:
                    self._flap_cassegrain_state = "04"
                    # Remove the parameter, as closing has finished:
                    _ = self.loaded_parameters.pop("cassegrain_flap", None)
                    logger.debug("set cassegran flap to CLOSED [04]")
                    return
            else:
                raise ValueError(f"Unknown cassegrain_flap parameter '{param}'")
        # ...otherwise, nothing has changed.
        return

    def move_flap_cassegrain(self, open_close: str):
        self.loaded_parameters["cassegrain_flap"] = open_close
        self._flap_cassegrain_starttime = time.time()
        self._update_flap_cassegrain_state()
        return

    def stop_flap_cassegrain(self):
        self.loaded_parameters["cassegrain_flap"] = "stop"
        self._update_flap_cassegrain_state()

    def get_flap_cassegrain_state(self):
        self._update_flap_cassegrain_state()
        return self._flap_cassegrain_state

    def _update_flap_mirror_state(self):
        param = self.loaded_parameters.get("mirror_flap", None)
        if param is not None:
            if param == "stop":
                self._flap_mirror_state = "00"  # stopped
                _ = self.loaded_parameters.pop("mirror_flap")
                return
            elif param in ["open", "1"]:
                if time.time() - self._flap_mirror_starttime < self.FLAP_TIME:
                    self._flap_mirror_state = "01"  # opening
                    logger.debug("set _mirror_flap_state to OPENING [01]")
                    return
                else:
                    self._flap_mirror_state = "03"  # open
                    _ = self.loaded_parameters.pop("mirror_flap", None)
                    logger.debug("set _mirror_flap_state to OPEN [03]")
                    return
            elif param in ["close", "0"]:
                if time.time() - self._flap_mirror_starttime < self.FLAP_TIME:
                    self._flap_mirror_state = "02"  # closing
                    logger.debug("set _mirror_flap_state to CLOSING [02]")
                    return
                else:
                    self._flap_mirror_state = "04"  # closed
                    _ = self.loaded_parameters.pop("mirror_flap", None)
                    logger.debug("set _mirror_flap_state to CLOSED [04]")
                    return
            else:
                raise ValueError(f"Unknown mirror_flap parameter '{param}'")
        return

    def move_flap_mirror(self, open_close: str):
        self.loaded_parameters["mirror_flap"] = open_close
        self._flap_mirror_starttime = time.time()
        self._update_flap_mirror_state()
        return

    def stop_flap_mirror(self):
        self.loaded_parameters["mirror_flap"] = "stop"
        self._update_flap_mirror_state()

    def get_flap_mirror_state(self):
        self._update_flap_mirror_state()
        logger.debug(f"return _flap_mirror_state {self._flap_mirror_state}")
        return self._flap_mirror_state

    def init_dome(self):
        self._dome_init_starttime = time.time()
        self._update_dome_state()

    def auto_dome(self):
        self._dome_auto = True
        self._dome_stopped = False
        self._dome_parking = False
        self._update_dome_state()

    def park_dome(self):
        self._dome_auto = False
        self._dome_stopped = False
        self._dome_parking = True
        self.set_dome_position(self.DOME_PARKED_POSITION)
        self.go_dome_position()

    def stop_dome(self):
        self._dome_parking = False
        self._dome_moving = False
        self._dome_auto = False
        self._dome_stopped = True
        _ = self.loaded_parameters.pop("dome_delta", None)
        self.dome_move_time = None
        self._update_dome_state()

    def _get_dome_str(self):
        return (
            "Dome:\n"
            f"    dome_pos: {self._dome_position}\n"
            f"    dome_delta: {self.loaded_parameters.get('dome_delta')}\n"
            f"    dome_move_time: {self.dome_move_time}\n"
            f"    dome_stopped: {self._dome_stopped}\n"
            f"    dome_auto: {self._dome_auto}\n"
            f"    dome_moving: {self._dome_moving}\n"
            f"    dome_parking: {self._dome_parking}\n"
            f"    last state set: {self._dome_state}\n"
        )

    def _update_dome_state(self):
        self._update_dome_position()
        dome_str = self._get_dome_str()

        if self._dome_stopped:
            if self._dome_moving:
                raise ValueError(
                    f"{dome_str}Can't be both _dome_stopped and _dome_auto!"
                )
            _ = self.loaded_parameters.pop("dome_delta", None)
            self._dome_state = "00"

        elif self._dome_moving:
            dome_delta = self.loaded_parameters.get("dome_delta", None)
            if dome_delta is None:
                raise ValueError(f"{dome_str}Can't be _dome_moving and no dome_delta")

            if self._dome_parking:
                if self._dome_auto:
                    msg = f"{dome_str}Can't be both dome_parking and _dome_auto!"
                    raise ValueError(msg)
                self._dome_state = "08"

            elif self._dome_auto:
                if dome_delta < 0:
                    self._dome_state = "04"
                else:
                    self._dome_state = "05"
            else:
                if dome_delta < 0:
                    self._dome_state = "06"
                else:
                    self._dome_state = "07"
        else:
            if self._dome_auto:
                self._dome_state = "03"  # auto
            else:
                msg = f"{dome_str}not moving, not auto, not stopped? don't know this state."
                raise ValueError(msg)
        return

    def _update_dome_position(self):
        dome_str = self._get_dome_str()
        dome_delta = self.loaded_parameters.get("dome_delta", None)
        if dome_delta is not None:
            if not self._dome_moving:
                msg = f"{dome_str}why is _dome_moving==False if dome_delta not None?"
                raise ValueError(msg)
            dt = time.time() - self._dome_move_starttime
            old_dome_pos = self.loaded_parameters["old_dome_pos"]
            if self.dome_move_time is None:
                raise ValueError("dome_move_time not correctly set.")

            f = dt / self.dome_move_time  # fraction of time through dome move.
            if f < 0:
                raise ValueError("dt<0: something has gone wrong...")
            if f < 1:
                inter_pos = old_dome_pos + f * dome_delta
                self._dome_position = inter_pos % 360.0
            else:
                # We have finished moving...
                _ = self.loaded_parameters.pop("old_dome_pos")
                _ = self.loaded_parameters.pop("dome_delta")
                new_dome_pos = old_dome_pos + dome_delta
                self._dome_position = new_dome_pos % 360.0
                self._dome_moving = False
                self.dome_move_time = None  # reset the dome move time.

                if self._dome_parking:
                    self._dome_stopped = True
                    self._dome_parking = False
        # else nothing changes.
        return

    def get_dome_state(self):
        self._update_dome_state()
        return self._dome_state

    def set_dome_position(self, dome_pos):
        if dome_pos < 0 or dome_pos > 360.0:
            raise ValueError(f"0.0<dome_pos<360.0, not {dome_pos}")

        dome_diff = dome_pos - self._dome_position
        dome_delta = (dome_diff + 180.0) % 360.0 - 180.0
        # dome_delta is signed, eg. moving 350deg to 10deg = 20, not 240.
        self.loaded_parameters["dome_delta"] = dome_delta

    def go_dome_position(self):
        dome_delta = self.loaded_parameters.get("dome_delta", None)
        if dome_delta is None:
            raise ValueError(
                "dome_delta (signed angle dome has to move) is not set correctly."
            )
        self.dome_move_time = abs(dome_delta) / self.DOME_MOVE_RATE
        self.loaded_parameters["old_dome_pos"] = self._dome_position
        self._dome_moving = True
        self._dome_move_starttime = time.time()

        self._update_dome_state()

    def _check_dome_position(self):
        self._update_telescope_state()
        if self._dome_auto:
            dome_offset = self._altaz.az.deg - self._dome_position
            if abs(dome_offset) > self.MAX_AUTO_DOME_OFFSET:
                self.set_dome_position(self._altaz.az.deg)
                self.go_dome_position()
        self._update_dome_state()

    def get_dome_position(self):
        self._check_dome_position()
        return self._dome_position

    def move_dome_slit(self, open_close: str):
        self.loaded_parameters["dome_slit_state"] = open_close
        self._dome_slit_starttime = time.time()
        self.set_dome_slit_state()

    def get_dome_slit_state(self):
        self.set_dome_slit_state()
        return self._dome_slit_state

    def set_dome_slit_state(self):
        param = self.loaded_parameters.get("dome_slit_state", None)
        if param is not None:
            if param == "stop":
                self._dome_slit_state = "00"
                _ = self.loaded_parameters.pop("dome_slit_state")
                return
            elif param in ["open", "1"]:
                if time.time() - self._dome_slit_starttime < self.DOME_SLIT_TIME:
                    self._dome_slit_state = "01"
                else:
                    self._dome_slit_state = "03"
                    _ = self.loaded_parameters.pop("dome_slit_state")
                return
            elif param in ["close", "0"]:
                if time.time() - self._dome_slit_starttime < self.DOME_SLIT_TIME:
                    self._dome_slit_state = "02"
                else:
                    self._dome_slit_state = "04"
                    _ = self.loaded_parameters.pop("dome_slit_state")
                return
            else:
                raise ValueError(f"Unknown dome_slit_state paramater '{param}'")
        return

    def set_shutter_pos(self, open_close: str):
        if open_close not in ["0", "1"]:
            msg = f"Unknown shutter position {open_close}: use '0' or '1'"
            logger.error(msg)
            raise ValueError(msg)
        self._shutter_pos = open_close

    def get_shutter_pos(self) -> str:
        return self._shutter_pos

    def set_focus_position(self, pos: float):
        self.loaded_parameters["focus_position"] = pos
        move_is_positive = pos >= self._focus_pos
        self.loaded_parameters["focus_moving_positive"] = move_is_positive

    def go_focus_position(self):
        focus_position = self.loaded_parameters.get("focus_position", None)
        if focus_position is None:
            msg = "Focus position not set! Use FOSA or FOSR first."
        self._focus_starttime = time.time()
        self._focus_pos = focus_position

    def get_focus_pos(self) -> float:
        return self._focus_pos

    def set_focus_state(self):
        focus_position = self.loaded_parameters.get("focus_position", None)
        focus_moving_positive = self.loaded_parameters.get(
            "focus_moving_positive", None
        )
        if focus_position is not None:
            if time.time() - self._focus_starttime < self.FOCUS_TIME:
                if focus_moving_positive is None:
                    raise ValueError("focus_moving_positive not correctly loaded...")
                if focus_moving_positive:
                    self._focus_state = "01"
                else:
                    self._focus_state = "02"
            else:
                # Moving is finished! Remove the loaded parameters...
                _ = self.loaded_parameters.pop("focus_position", None)
                _ = self.loaded_parameters.pop("focus_moving_positive")
                self._focus_state = "00"
        logger.debug(f"set _focus_state {self._focus_state}")
        return

    def get_focus_state(self):
        self.set_focus_state()
        return self._focus_state
