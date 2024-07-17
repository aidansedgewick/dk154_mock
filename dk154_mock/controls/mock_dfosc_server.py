import string
import time
import traceback
from logging import getLogger

from astropy.time import Time

from dk154_mock.controls.base_servers.mock_tcp_base import MockTCPServer
from dk154_mock.hardware.mock_observatory import MockDk154

logger = getLogger("MockDfoscServer")


class MockDfoscServer(MockTCPServer):
    def __init__(self, obs: MockDk154, port: int = 8883):
        super().__init__(port=port, reply_cb=self.dfosc_callback, server_name="dfosc")

        self.obs = obs
        self.loaded_parameters = {}
        self._set_responders()

    def dfosc_callback(self, command: str):
        if isinstance(command, bytes):
            command = command.decode("utf-8")
        command = command.rstrip()

        logger.info(f"command is '{command}' = {command.split()}")

        # Get the correct responder. Think carefully, as commands have different lengths.
        if command.lower() in ["g", "a", "f", "gidfoc", "aidfoc", "fidfoc"]:
            responder_code = command
        else:
            responder_code = command[:2]
            if responder_code[1] in "0123456789":
                # ie: G5, A2, F6...
                responder_code = responder_code[0] + "N"  # eg. 'G5' -> 'GN'
            responder_code = responder_code.lower()

        response_function = self.responders_lookup.get(responder_code, None)
        if response_function is not None:
            logger.info(f"responding to {responder_code}...")
            try:
                response = response_function(command)
                response = response or ""  # Don't want 'None' as response...
                if isinstance(response, tuple):
                    response = " ".join(str(x) for x in response)
                logger.info(f"successful response {response}")
                response = response + "\n"
            except Exception as e:
                logger.error(f"exception {type(e)}: {e}")
                tr = traceback.format_exc()
                logger.error(f"traceback \n:{tr}")
                return "ERR"
            logger.info(f"return response {repr(response)}")
            return response
        logger.error(f"\033[31;1mNo responder for {responder_code}.\033[0m Return ERR.")
        return "ERR"

    def _set_responders(self):
        self.responders_lookup = {
            "gi": self.gi_response,
            "gg": self.gg_response,
            "gm": self.gm_response,
            "gp": self.gp_response,
            "gn": self.gn_response,
            "gq": self.gq_response,
            "gx": self.gx_response,
            "g": self.g_response,
            "aidfoc": self.gidfoc_response,
            "ai": self.ai_response,
            "ag": self.ag_response,
            "am": self.am_response,
            "ap": self.ap_response,
            "an": self.an_response,
            "aq": self.aq_response,
            "ax": self.ax_response,
            "a": self.a_response,
            "aidfoc": self.aidfoc_response,
            "fi": self.fi_response,
            "fg": self.fg_response,
            "fm": self.fm_response,
            "fp": self.fp_response,
            "fn": self.fn_response,
            "fq": self.fq_response,
            "fx": self.fx_response,
            "f": self.f_response,
            "fidfoc": self.fidfoc_response,
        }

    def gi_response(self, command: str):
        raise NotImplementedError

    def gg_response(self, command: str):
        pos = int(command[2:])
        logger.info(f"DFOSC grism move to {pos}")
        self.obs.dfosc.grism_move_position(pos)
        return command

    def gm_response(self, command: str):
        rel_pos = int(command[2:])
        curr_pos = self.obs.dfosc.get_grism_position()
        pos = curr_pos + rel_pos
        logger.info(f"DFOSC grism move to {pos}")
        self.obs.dfosc.grism_move_position(pos)
        return command

    def gp_response(self, command: str):
        curr_pos = self.obs.dfosc.get_grism_position()
        pos_str = f"{curr_pos:06d}"
        return pos_str

    def gn_response(self, command: str):
        n = int(command[1])
        pos = n * self.obs.dfosc.INTEGER_STEP
        self.obs.dfosc.grism_move_position(pos)
        return command

    def gq_response(self, command: str):
        raise NotImplementedError

    def g_response(self, command: str):
        grism_ready = self.obs.dfosc.check_grism_ready()
        if grism_ready:
            return "y"
        return "n"

    def gx_response(self, command: str):
        self.obs.dfosc.grism_move_position(0)
        return command

    def gidfoc_response(self, command: str):
        raise NotImplementedError

    def ai_response(self, command: str):
        raise NotImplementedError

    def ag_response(self, command: str):
        pos = int(command[2:])
        logger.info(f"DFOSC aperture move to {pos}")
        self.obs.dfosc.aperture_move_position(pos)
        return command

    def am_response(self, command: str):
        rel_pos = int(command[2:])
        curr_pos = self.obs.dfosc.get_aperture_position()
        pos = curr_pos + rel_pos
        logger.info(f"DFOSC aperture move to {pos}")
        self.obs.dfosc.aperture_move_position(pos)
        return command

    def ap_response(self, command: str):
        curr_pos = self.obs.dfosc.get_aperture_position()
        pos_str = f"{curr_pos:06d}"
        return pos_str

    def an_response(self, command: str):
        n = int(command[1])
        pos = n * self.obs.dfosc.INTEGER_STEP
        self.obs.dfosc.aperture_move_position(pos)
        return command

    def a_response(self, command: str):
        aperture_ready = self.obs.dfosc.check_aperture_ready()
        if aperture_ready:
            return "y"
        return "n"

    def aq_response(self, command: str):
        raise NotImplementedError

    def ax_response(self, command: str):
        self.obs.dfosc.aperture_move_position(0)
        return command

    def aidfoc_response(self, command: str):
        raise NotImplementedError

    def fi_response(self, command: str):
        raise NotImplementedError

    def fg_response(self, command: str):
        pos = int(command[2:])
        logger.info(f"DFOSC aperture move to {pos}")
        self.obs.dfosc.filter_move_position(pos)
        return command

    def fm_response(self, command: str):
        rel_pos = int(command[2:])
        curr_pos = self.obs.dfosc.get_filter_position()
        pos = curr_pos + rel_pos
        logger.info(f"DFOSC filter move to {pos}")
        self.obs.dfosc.filter_move_position(pos)
        return command

    def fp_response(self, command: str):
        curr_pos = self.obs.dfosc.get_filter_position()
        pos_str = f"{curr_pos:06d}"
        return pos_str

    def fn_response(self, command: str):
        n = int(command[1])
        pos = n * self.obs.dfosc.INTEGER_STEP
        self.obs.dfosc.filter_move_position(pos)
        return command

    def f_response(self, command: str):
        filter_ready = self.obs.dfosc.check_filter_ready()
        if filter_ready:
            return "y"
        return "n"

    def fq_response(self, command: str):
        raise NotImplementedError

    def fx_response(self, command: str):
        self.obs.dfosc.filter_move_position(0)
        return command

    def fidfoc_response(self, command: str):
        raise NotImplementedError
