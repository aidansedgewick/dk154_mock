import time
from logging import getLogger

from astropy.time import Time, TimeDelta

logger = getLogger("MockTelescope")


class MockTelescope:

    LOGIN_TIMEOUT = 120.0
    SLEW_TIME = 10.0
    WHEEL_TIME = 7.0
    FLAP_TIME = 8.0
    DOME_SLIT_TIME = 8.0
    PARK_TIME = 10.0

    FOCUS_TIME = 3.0
    FOCUS_MIN_POS = -50.0
    FOCUS_MAX_POS = 50.0

    def __init__(self, t_start: Time = None):

        self.t_start = t_start or Time.now()  # "Fake time"
        self.t_init = time.time()  # To count 'real' time since telescope started.

        self._remote_state = "0"
        self._safety_relay_state = "0"
        self._tel_state = "05"
        self._dome_state = "03"
        self._dome_slit_state = "03"
        self._shutter_pos = "0"

        self._wheel_a_pos = "0"
        self._wheel_a_state = "00"
        self._wheel_a_starttime = 0.0  # Timer
        self._wheel_b_moving = False
        self._wheel_b_pos = "0"
        self._wheel_b_state = "00"
        self._wheel_b_starttime = 0.0  # Timer
        self._wheel_b_moving = False

        self._ra = 45.0
        self._dec = -30.50833
        self._tel_pos = "0"
        self._tel_stopped = True
        self._slew_starttime = 0.0

        self._logged_in = False
        self._login_time = 0.0

        self._flap_cassegrain_state = "00"
        self._flap_cassegrain_starttime = 0.0
        self._flap_mirror_state = "00"
        self._flap_mirror_starttime = 0.0

        self._focus_pos = 0.0
        self._focus_state = "00"
        self._focus_starttime = 0.0

        self.loaded_parameters = {}

    @classmethod
    def start_in_ready_state(cls):
        telescope = cls()
        telescope._tel_state = "05"
        return telescope

    def update_login_status(self):
        if time.time() - self._login_time > self.LOGIN_TIMEOUT:
            self._logged_in = False
        return

    def get_login_status(self):
        self.update_login_status()
        return self._logged_in

    def get_t_ref(self):
        return self.t_start + TimeDelta(time.time() - self.t_init, format="sec")

    def set_telescope_position(self, ra, dec, tel_pos):
        self.loaded_parameters["ra"] = ra
        self.loaded_parameters["dec"] = dec
        self.loaded_parameters["tel_pos"] = tel_pos

    def go_telescope_position(self):
        ra = self.loaded_parameters.pop("ra", None)
        dec = self.loaded_parameters.pop("dec", None)
        tel_pos = self.loaded_parameters.pop("tel_pos", None)
        if any([x is None for x in [ra, dec, tel_pos]]):
            msg = f"One of ra={ra}, dec={dec}, pos={tel_pos} not set. Use TSRA!"
            raise ValueError(msg)
        self._tel_stopped = False
        self._slew_starttime = time.time()
        self._ra = ra
        self._dec = dec
        self._tel_pos = tel_pos
        return

    def get_telescope_position(self):
        return self._ra, self._dec, self._tel_pos

    def set_telescope_state(self):
        if self._tel_stopped:
            self._tel_state = "04"
        else:
            if time.time() - self._slew_starttime < self.SLEW_TIME:
                self._tel_state = "07"
            else:
                self._tel_state = "05"
        return

    def get_telescope_state(self):
        self.set_telescope_state()
        return self._tel_state

    def go_wheel_a(self):
        wheel_a_pos = self.loaded_parameters.pop("wheel_a_pos", None)
        if wheel_a_pos is None:
            msg = f"wheel_b_pos not set! use WASP first."
            logger.error(msg)
            raise ValueError(msg)
        self._wheel_a_starttime = time.time()
        self._wheel_a_pos = wheel_a_pos

    def set_wheel_a_state(self):
        """Check if the wheel is moving, or stopped/ready, set the state accordingly"""
        if time.time() - self._wheel_a_starttime < self.WHEEL_TIME:
            self._wheel_a_state = "03"
        else:
            self._wheel_a_state = "00"

    def get_wheel_a_state(self) -> str:
        self.set_wheel_a_state()
        return self._wheel_a_state

    def set_wheel_a_pos(self, wheel_a_pos):
        """Load the position into the system, but not actually move there"""
        self.loaded_parameters["wheel_a_pos"] = wheel_a_pos
        return

    def get_wheel_a_pos(self) -> str:
        self.set_wheel_a_state()
        if self._wheel_a_state != "00":
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
            self._wheel_b_state = "03"
        else:
            self._wheel_b_state = "00"
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
        if self._wheel_b_state != "00":
            return "7"  # rotating
        return self._wheel_b_pos

    def set_flap_cassegrain_state(self):
        param = self.loaded_parameters.get("cassegrain_flap", None)
        if param is not None:
            if param == "stop":
                self._flap_cassegrain_state = "00"
                _ = self.loaded_parameters.pop("cassegrain_flap")
                return
            if param in ["open", "1"]:
                if time.time() - self._flap_cassegrain_starttime < self.FLAP_TIME:
                    self._flap_cassegrain_state == "01"
                    logger.info("set cassegrain flap to opening")
                    return
                else:
                    self._flap_cassegrain_state == "03"
                    # Remove the parameter, as opening has finished:
                    _ = self.loaded_parameters.pop("cassegrain_flap", None)
                    logger.info("set cassegrain flap to OPEN")
                    return
            if param in ["close", "0"]:
                if time.time() - self._flap_cassegrain_starttime < self.FLAP_TIME:
                    self._flap_cassegrain_state == "02"
                    logger.info("set cassegrain flap to opening")
                    return
                else:
                    self._flap_cassegrain_state == "04"
                    # Remove the parameter, as closing has finished:
                    _ = self.loaded_parameters.pop("cassegrain_flap", None)
                    logger.info("set cassegran flap to OPEN")
                    return
            raise ValueError(f"Unknown cassegrain_flap parameter '{param}'")
        # ...otherwise, nothing has changed.
        return

    def move_flap_cassegrain(self, open_close: str):
        self.loaded_parameters["cassegrain_flap"] = open_close
        self._flap_cassegrain_starttime = time.time()
        return

    def get_flap_cassegrain_state(self):
        self.set_flap_cassegrain_state()
        return self._flap_cassegrain_state

    def set_flap_mirror_state(self):
        param = self.loaded_parameters.get("mirror_flap", None)
        if param is not None:
            if param == "stop":
                self._flap_mirror_state = "00"
                _ = self.loaded_parameters.pop("mirror_flap")
                return
            if param in ["open", "1"]:
                if time.time() - self._flap_mirror_starttime < self.FLAP_TIME:
                    self._flap_mirror_state == "01"
                    logger.info("set mirror flap to opening")
                    return
                else:
                    self._flap_mirror_state == "03"
                    _ = self.loaded_parameters.pop("mirror_flap", None)
                    logger.info("set mirror flap to OPEN")
                    return
            if param in ["close", "0"]:
                if time.time() - self._flap_mirror_starttime < self.FLAP_TIME:
                    self._flap_mirror_state == "02"
                    logger.info("set mirror flap to opening")
                    return
                else:
                    self._flap_mirror_state == "04"
                    _ = self.loaded_parameters.pop("mirror_flap", None)
                    logger.info("set mirror flap to OPEN")
                    return
            raise ValueError(f"Unknown mirror_flap parameter '{param}'")
        return

    def move_flap_mirror(self, open_close: str):
        self.loaded_parameters["mirror_flap"] = open_close
        self._flap_mirror_starttime = time.time()
        return

    def get_flap_mirror_state(self):
        self.set_flap_mirror_state()
        return self._flap_mirror_state

    def set_dome_state(self):
        return

    def get_dome_state(self):
        self.set_dome_state()
        return self._dome_state

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
                return
            else:
                # Moving is finished! Remove the loaded parameters...
                _ = self.loaded_parameters.pop("focus_position", None)
                _ = self.loaded_parameters.pop("focus_moving_positive")
                self._focus_state = "00"
                return
        return

    def get_focus_state(self):
        self.set_focus_state()
        return self._focus_state
