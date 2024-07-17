import asyncio
import time
import traceback
from logging import getLogger

from astropy.coordinates import Angle
from astropy.time import Time

from dk154_control.utils import dec_dms_to_deg, ra_hms_to_deg
from dk154_mock.controls.base_servers.mock_tcp_base import MockTCPServer
from dk154_mock.hardware.mock_observatory import MockDk154

logger = getLogger("MockAscolServer")


class MockAscolServer(MockTCPServer):

    REQUIRE_LOGIN = ["TSRA", "TGRA", "WASP", "WAGP", "WBSP", "WBGP"]

    def __init__(self, obs: MockDk154, port: int = 8888, loop=None):
        super().__init__(port=port, reply_cb=self.ascol_callback, server_name="ascol")

        self.obs = obs
        self.loaded_parameters = {}
        self._set_responders()

    def ascol_callback(self, command: str):
        if isinstance(command, bytes):
            command = command.decode("utf-8")
        command = command.rstrip()

        logger.info(f"got cmd: '{command}' = {command.split()}")
        command_code = command.split()[0]

        if self.obs.telescope._tel_state == "00":
            logger.error("telescope is off!")
            return "ERR"

        if command_code in self.REQUIRE_LOGIN:
            logged_in = self.check_login_state()
            if not logged_in:
                logger.error(f"{command_code} requires GLLG!")
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
                tr = traceback.format_exc()
                logger.error(f"traceback \n:{tr}")
                return "ERR"
            logger.info(f"return response {response}")
            return response
        logger.error(f"\033[31;1mNo responder for {command_code}.\033[0m Return ERR.")
        return "ERR"

    def check_login_state(self):
        return self.obs.telescope.get_login_status()

    def _set_responders(self):
        """
        TODO: This is gross, there must be a better way to do it...
        """

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
            "FOSA": self.fosa_response,
            "FOSR": self.fosr_response,
            "FOGA": self.foga_response,
            "FOGR": self.fogr_response,
            "FORA": self.fora_response,
            "FOMI": self.fomi_response,
            "FOMA": self.foma_response,
            "FORS": self.fors_response,
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

    ### Response codes ###

    def glre_response(self, command: str):
        return self.obs.telescope._remote_state, "---"

    def gslr_response(self, command: str):
        return self.obs.telescope._safety_relay_state, "---"

    def gllg_response(self, command: str):
        self.obs.telescope._logged_in = True
        self.obs.telescope._login_time = time.time()
        return "1", "---"

    def glll_response(self, command: str):
        raise NotImplementedError()

    def glut_response(self, command: str):
        t_now = self.obs.telescope.get_t_ref()
        return int(t_now.mjd), t_now.strftime("%H%M%S.%f"), "---"

    def glsd_response(self, command: str):
        t_now = self.obs.telescope.get_t_ref()
        return t_now.strftime("%H%M%S.%f"), "---"

    def teon_response(self, command: str):
        raise NotImplementedError()

    def test_response(self, command: str):
        self.obs.telescope._tel_stopped = True
        return "1", "---"

    def tefl_response(self, command: str):
        raise NotImplementedError

    def tepa_response(self, command: str):
        raise NotImplementedError()

    def tsra_response(self, command: str):
        code, ra_str, dec_str, tel_pos = command.split()
        ra = ra_hms_to_deg(ra_str)
        dec = dec_dms_to_deg(dec_str)
        self.obs.telescope.set_telescope_position(ra, dec, tel_pos)
        return "1"

    def tgra_response(self, command: str):
        self.obs.telescope.go_telescope_position()
        return "1"

    def trrd_response(self, command: str):
        ra, dec, tel_pos = self.obs.telescope.get_telescope_position()

        ra_hms = Angle(ra, unit="deg").hms
        ra_str = f"{int(ra_hms.h):02d}{int(ra_hms.m):02d}{ra_hms.s:.2f}"

        dec_dms = Angle(dec, unit="deg").dms
        dec_str = f"{int(dec_dms.d):+02d}{int(dec_dms.m):02d}{dec_dms.s:.2f}"

        return ra_str, dec_str, tel_pos, "---"

    def ters_response(self, commmand):
        return self.obs.telescope.get_telescope_state(), "---"

    def dopa_response(self, command: str):
        return "1", "---"

    def dost_response(self, command: str):
        return "1", "---"

    def dors_response(self, command: str):
        return self.obs.telescope.get_dome_state(), "---"

    def fcop_response(self, command: str):
        code, open_close = command.split()
        self.obs.telescope.move_flap_cassegrain(open_close)
        return "1", "---"

    def fcrs_response(self, command: str):
        return self.obs.telescope.get_flap_cassegrain_state(), "---"

    def fmop_response(self, command: str):
        code, open_close = command.split()
        self.obs.telescope.move_flap_mirror(open_close)
        return "1", "---"

    def fmrs_response(self, command: str):
        return self.obs.telescope.get_flap_mirror_state(), "---"

    def wasp_response(self, command: str):
        code, wheel_a_pos = command.split()
        self.obs.telescope.set_wheel_a_pos(wheel_a_pos)
        return "1", "---"

    def wagp_response(self, command: str):
        self.obs.telescope.go_wheel_a()
        return "1", "---"

    def warp_response(self, command: str):
        return self.obs.telescope.get_wheel_a_pos(), "---"

    def wars_response(self, command: str):
        return self.obs.telescope.get_wheel_a_state(), "---"

    def wbsp_response(self, command: str):
        code, wheel_b_pos = command.split()
        self.obs.telescope.set_wheel_b_pos(wheel_b_pos)
        return "1", "---"

    def wbgp_response(self, command: str):
        self.obs.telescope.go_wheel_b()
        return "1", "---"

    def wbrp_response(self, command: str):
        return self.obs.telescope.get_wheel_b_pos(), "---"

    def wbrs_response(self, command: str):
        return self.obs.telescope.get_wheel_b_state(), "---"

    def fosa_response(self, command: str):
        code, focus_str = command.split()
        focus_pos = float(focus_str)
        self.obs.telescope.set_focus_position(focus_pos)
        return "1", "---"

    def fosr_response(self, command: str):
        code, focus_rel_str = command.split()
        focus_rel_pos = float(focus_rel_str)
        focus_curr_pos = self.obs.telescope.get_focus_pos()
        focus_pos = focus_curr_pos + focus_rel_pos
        self.obs.telescope.set_focus_position()

    def foga_response(self, command: str):
        self.obs.telescope.go_focus_position()

    def fogr_response(self, command: str):
        self.obs.telescope.go_focus_position()

    def foat_response(self, command: str):
        raise NotImplementedError()

    def fost_response(self, command: str):
        raise NotImplementedError()

    def fora_response(self, command: str):
        focus_pos = self.obs.telescope.get_focus_pos()
        focus_str = f"{focus_pos:.02f}"
        return focus_str

    def fomi_response(self, command: str):
        focus_min_str = self.obs.telescope.FOCUS_MIN_POS
        return f"{focus_min_str:.02f}"

    def foma_response(self, command: str):
        focus_max_str = self.obs.telescope.FOCUS_MAX_POS
        return f"{focus_max_str:.02f}"

    def fotc_response(self, command: str):
        raise NotImplementedError()

    def fors_response(self, command: str):
        return self.obs.telescope.get_focus_state()

    def shop_response(self, command: str):
        code, open_close = command.split()
        self.obs.telescope.set_shutter_pos(open_close)
        return "1", "---"

    def shrp_response(self, command: str):
        return self.obs.telescope.get_shutter_pos(), "---"

    def mebe_response(self, command: str):
        return 100.00, "1", "---"

    def mebn_response(self, command: str):
        return 200.00, "1", "---"

    def mebw_response(self, command: str):
        return 400.00, "1", "---"

    def metw_response(self, command: str):
        return 250.0, "1", "---"

    def mehu_response(self, command: str):
        return 10, "1", "---"

    def mete_response(self, command: str):
        return 12.5, "1", "---"

    def mews_response(self, command: str):
        return 5.00, "1", "---"

    def mepr_response(self, command: str):
        return "0", "1", "---"

    def meap_response(self, command: str):
        return 678.4, "1", "---"

    def mepy_response(self, command: str):
        return 5.00, "1", "---"

    def doss_response(self, command: str):
        return self.obs.telescope._dome_slit_state, "---"
