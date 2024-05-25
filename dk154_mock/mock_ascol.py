import asyncio
import time
from logging import getLogger

from astropy.time import Time

from dk154_mock.mock_tcp_base import MockTCPServer

logger = getLogger("MockAscolServer")


class MockAscolServer(MockTCPServer):

    # REQUIRE_LOGIN = ["WASP", "WAGP", "WBSP", "WBGP"]

    LOGIN_TIMEOUT = 120.0
    SLEW_TIME = 10.0
    WHEEL_TIME = 7.0
    FLAP_TIME = 8.0
    DOME_SLIT_TIME = 8.0
    PARK_TIME = 10.0

    def __init__(self, port=8888, loop=None):
        super().__init__(port=port, reply_cb=self.callback)

        self.remote_state = "0"
        self.safety_relay_state = "0"
        self.telescope_state = "05"
        self.dome_state = "03"
        self.dome_slit_state = "03"
        self.shutter_pos = "0"

        self.wheel_a_pos = "0"
        self.wheel_a_status = "00"
        self.wheel_a_start = 0.0
        self.wheel_b_moving = False
        self.wheel_b_pos = "0"
        self.wheel_b_status = "00"
        self.wheel_b_start = 0.0
        self.wheel_b_moving = False

        self.ra = "030000.0"
        self.dec = "-303030.0"
        self.tel_pos = "0"
        self.tel_stopped = True
        self.slew_start = 0.0

        self.logged_in = False
        self.login_time = 0.0

        self.flap_cassegrain_state = "00"
        self.flap_cassegrain_start = 0.0
        self.flap_mirror_state = "00"
        self.flap_mirror_start = 0.0

        self.loaded_parameters = {}

        self.set_responders()

    @classmethod
    def start_ready(cls):
        raise NotImplementedError()
        server = cls()
        server.telescope_state = "05"
        return server

    def callback(self, command):
        if isinstance(command, bytes):
            command = command.decode("utf-8")
        command = command.rstrip()

        logger.info(f"command is '{command}' = {command.split()}")
        command_code = command.split()[0]

        if self.telescope_state == "00":
            logger.error("telescope is off!")
            return "ERR"

        responder = self.responders_lookup.get(command_code, None)
        if responder is not None:
            logger.info(f"responding to {command_code}...")
            try:
                response = responder(command)
                if isinstance(response, tuple):
                    response = " ".join(str(x) for x in response)
                logger.info(f"successful response {response}")
            except Exception as e:
                logger.error(f"exception {type(e)}: {e}")
                return "ERR"
            logger.info(f"return response {response}")
            return response
        logger.error(f"\033[31;1mNo responder for {command_code}.\033[0m Return ERR.")
        return "ERR"

    def set_responders(self):
        self.responders_lookup = {
            "GLRE": self.glre_response,
            "GLSR": self.gslr_response,
            "GLLG": self.gllg_response,
            "GLLL": self.glll_response,
            "GLUT": self.glut_response,
            "GLSD": self.glsd_response,
            "TGRA": self.tgra_response,
            "TEON": self.teon_response,
            "TEST": self.test_response,
            "TEFL": self.tefl_response,
            "TEPA": self.tepa_response,
            "TSRA": self.tsra_response,
            "TERS": self.ters_response,
            "DORS": self.dors_response,
            "FCRS": self.fcrs_response,
            "FCOP": self.fcop_response,
            "FMRS": self.fmrs_response,
            "FMOP": self.fmop_response,
            "TRRD": self.trrd_response,
            "WASP": self.wasp_response,
            "WAGP": self.wagp_response,
            "WARP": self.warp_response,
            "WARS": self.wars_response,
            "WBSP": self.wbsp_response,
            "WBGP": self.wbgp_response,
            "WBRP": self.wbrp_response,
            "WBRS": self.wbrs_response,
            "SHOP": self.shop_response,
            "SHRP": self.shrp_response,
            "MEBE": self.mebe_response,
            "MEBN": self.mebn_response,
            "MEBW": self.mebw_response,
            "METW": self.metw_response,
            "MEHU": self.mehu_response,
            "METE": self.mete_response,
            "MEWS": self.mews_response,
            "MEPR": self.mepr_response,
            "MEAP": self.meap_response,
            "MEPY": self.mepy_response,
            "DOSS": self.doss_response,
        }

    def update_login_status(self):
        if time.time() - self.login_time > self.LOGIN_TIMEOUT:
            self.logged_in = False
        return

    def set_telescope_position(self):
        ra = self.loaded_parameters.pop("ra", None)
        dec = self.loaded_parameters.pop("dec", None)
        tel_pos = self.loaded_parameters.pop("tel_pos", None)
        if any([x is None for x in [ra, dec, tel_pos]]):
            msg = f"One of ra={ra}, dec={dec}, pos={tel_pos} not set. Use TSRA!"
            raise ValueError(tel_pos)
        self.tel_stopped = False
        self.slew_start = time.time()
        self.ra = ra
        self.dec = dec
        self.tel_pos = tel_pos
        return

    def set_telescope_state(self):
        if self.tel_stopped:
            self.telescope_state = "04"
        else:
            if time.time() - self.slew_start < self.SLEW_TIME:
                self.telescope_state = "07"
            else:
                self.telescope_state = "05"
        return

    def get_telescope_state(self):
        self.set_telescope_state()
        return self.telescope_state

    def go_wheel_a(self):
        wheel_a_pos = self.loaded_parameters.get("wheel_a_pos", None)
        if wheel_a_pos is None:
            raise ValueError(f"wheel_b_pos not set! use WASP first.")
        self.wheel_a_start = time.time()
        self.wheel_a_pos = wheel_a_pos

    def set_wheel_a_state(self):
        if time.time() - self.wheel_a_start < self.WHEEL_TIME:
            self.wheel_a_state = "03"
        else:
            self.wheel_a_state = "00"

    def get_wheel_a_state(self):
        self.set_wheel_a_state()
        return self.wheel_a_state

    def get_wheel_a_pos(self):
        self.set_wheel_a_state()
        if self.wheel_a_state != "00":
            return "8"  # rotating
        return self.wheel_a_pos

    def go_wheel_b(self):
        wheel_b_pos = self.loaded_parameters.pop("wheel_b_pos", None)
        if wheel_b_pos is None:
            raise ValueError(f"wheel_b_pos not set! use WBSP first.")
        self.wheel_b_start = time.time()
        self.wheel_b_pos = wheel_b_pos

    def set_wheel_b_state(self):
        if time.time() - self.wheel_b_start < self.WHEEL_TIME:
            self.wheel_b_state = "03"
        else:
            self.wheel_b_state = "00"

    def get_wheel_b_state(self):
        self.set_wheel_b_state()
        return self.wheel_b_state

    def get_wheel_b_pos(self):
        self.set_wheel_b_state()
        if self.wheel_b_state != "00":
            return "7"  # rotating
        return self.wheel_b_pos

    def set_flap_cassegrain_state(self):
        param = self.loaded_parameters.get("cassegrain_flap", None)
        if param is not None:
            if param == "stop":
                self.flap_cassegrain_state = "00"
                _ = self.loaded_parameters.pop("cassegrain_flap")
                return
            if param in ["open", "1"]:
                if time.time() - self.flap_cassegrain_start < self.FLAP_TIME:
                    self.flap_cassegrain_state == "01"
                    logger.info("set cassegrain flap to opening")
                    return
                else:
                    self.flap_cassegrain_state == "03"
                    _ = self.loaded_parameters.pop("cassegrain_flap", None)
                    logger.info("set cassegrain flap to OPEN")
                    return
            if param in ["close", "0"]:
                if time.time() - self.flap_cassegrain_start < self.FLAP_TIME:
                    self.flap_cassegrain_state == "02"
                    logger.info("set cassegrain flap to opening")
                    return
                else:
                    self.flap_cassegrain_state == "04"
                    _ = self.loaded_parameters.pop("cassegrain_flap", None)
                    logger.info("set cassegran flap to OPEN")
                    return
            raise ValueError(f"Unknown cassegrain_flap parameter '{param}'")
        return

    def get_flap_cassegrain_state(self):
        self.set_flap_cassegrain_state()
        return self.flap_cassegrain_state

    def set_flap_mirror_state(self):
        param = self.loaded_parameters.get("mirror_flap", None)
        if param is not None:
            if param == "stop":
                self.flap_mirror_state = "00"
                _ = self.loaded_parameters.pop("mirror_flap")
                return
            if param in ["open", "1"]:
                if time.time() - self.flap_mirror_start < self.FLAP_TIME:
                    self.flap_mirror_state == "01"
                    logger.info("set mirror flap to opening")
                    return
                else:
                    self.flap_mirror_state == "03"
                    _ = self.loaded_parameters.pop("mirror_flap", None)
                    logger.info("set mirror flap to OPEN")
                    return
            if param in ["close", "0"]:
                if time.time() - self.flap_mirror_start < self.FLAP_TIME:
                    self.flap_mirror_state == "02"
                    logger.info("set mirror flap to opening")
                    return
                else:
                    self.flap_mirror_state == "04"
                    _ = self.loaded_parameters.pop("mirror_flap", None)
                    logger.info("set mirror flap to OPEN")
                    return
            raise ValueError(f"Unknown mirror_flap parameter '{param}'")
        return

    def get_flap_mirror_state(self):
        self.set_flap_mirror_state()
        return self.flap_mirror_state

    ### Response codes ###

    def glre_response(self, command):
        return self.remote_state, "---"

    def gslr_response(self, command):
        return self.safety_relay_state, "---"

    def gllg_response(self, command):
        self.logged_in = True
        self.login_time = time.time()
        return "1", "---"

    def glll_response(self, command):
        raise NotImplementedError()

    def glut_response(self, command):
        t_now = Time.now()
        return int(t_now.mjd), t_now.strftime("%H%M%S.%f"), "---"

    def glsd_response(self, command):
        t_now = Time.now()
        return t_now.strftime("%H%M%S.%f"), "---"

    def teon_response(self, command):
        raise NotImplementedError()

    def test_response(self, command):
        self.tel_stopped = True
        return "1", "---"

    def tefl_response(self, command):
        raise NotImplementedError

    def tepa_response(self, command):
        raise NotImplementedError()

    def tsra_response(self, command):
        code, ra, dec, tel_pos = command.split()
        self.loaded_parameters["ra"] = ra
        self.loaded_parameters["dec"] = dec
        self.loaded_parameters["tel_pos"] = tel_pos
        return "1"

    def tgra_response(self, command):
        self.set_telescope_position()
        return "1"

    def trrd_response(self, command):
        return self.ra, self.dec, self.tel_pos, "---"

    def ters_response(self, commmand):
        return self.get_telescope_state(), "---"

    def dopa_response(self, command):
        return "1", "---"

    def dost_response(self, command):
        return "1", "---"

    def dors_response(self, command):
        return self.dome_state, "---"

    def fcop_response(self, command):
        code, open_close = command.split()
        self.loaded_parameters["flap_cassegrain"] = open_close
        self.flap_cassegrain_start = time.time()
        return "1", "---"

    def fcrs_response(self, command):
        return self.get_flap_cassegrain_state(), "---"

    def fmop_response(self, command):
        code, open_close = command.split()
        self.loaded_parameters["flap_mirror"] = open_close
        self.flap_mirror_start = time.time()
        return "1", "---"

    def fmrs_response(self, command):
        return self.get_flap_mirror_state(), "---"

    def wasp_response(self, command):
        code, wheel_a_pos = command.split()
        self.loaded_parameters["wheel_a_pos"] = wheel_a_pos
        return "1", "---"

    def wagp_response(self, command):
        self.go_wheel_a()
        return "1", "---"

    def warp_response(self, command):
        return self.get_wheel_a_pos(), "---"

    def wars_response(self, command):
        return self.get_wheel_a_state(), "---"

    def wbsp_response(self, command):
        code, wheel_b_pos = command.split()
        self.loaded_parameters["wheel_b_pos"] = wheel_b_pos
        return "1", "---"

    def wbgp_response(self, command):
        self.go_wheel_b()
        return "1", "---"

    def wbrp_response(self, command):
        return self.get_wheel_b_pos(), "---"

    def wbrs_response(self, command):
        return self.get_wheel_b_state(), "---"

    def shop_response(self, command):
        code, open_close = command.split()
        self.shutter_pos = open_close
        return "1", "---"

    def shrp_response(self, command):
        return self.shutter_pos, "---"

    def mebe_response(self, command):
        return 100.00, "1", "---"

    def mebn_response(self, command):
        return 200.00, "1", "---"

    def mebw_response(self, command):
        return 400.00, "1", "---"

    def metw_response(self, command):
        return 250.0, "1", "---"

    def mehu_response(self, command):
        return 10, "1", "---"

    def mete_response(self, command):
        return 12.5, "1", "---"

    def mews_response(self, command):
        return 5.00, "1", "---"

    def mepr_response(self, command):
        return "0", "1", "---"

    def meap_response(self, command):
        return 678.4, "1", "---"

    def mepy_response(self, command):
        return 5.00, "1", "---"

    def doss_response(self, command):
        return self.dome_slit_state, "---"
