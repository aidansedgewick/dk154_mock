import time
from logging import getLogger

logger = getLogger("MockDfosc")


class MockDfosc:

    WHEEL_TIME = 12.0
    QUIT_TIME = 1.0
    MAX_POSITION = 320000
    INTEGER_STEP = 40000

    def __init__(self):
        self._grism_ready = True
        self._aperture_ready = True
        self._filter_ready = True

        self._grism_position = 120000
        self._aperture_position = 240000
        self._filter_position = 160000

        # self._grism_zero_position = 0  # ie, offset ?
        # self._aperture_zero_position = 0
        # self._filter_zero_position = 0

        # self._grism_prev_position = 0
        # self._aperture_prev_position = 0
        # self._filter_prev_position = 0

        self._grism_move_start = 0.0  # timers
        self._aperture_move_start = 0.0
        self._filter_move_start = 0.0

    @classmethod
    def start_in_ready_state(cls):
        dfosc = cls()
        # Set these by hand, in case want to add time delay to init_grism(), etc.
        dfosc._grism_ready = True
        dfosc._aperture_ready = True
        dfosc._filter_ready = True
        return dfosc

    def init_grism(self):
        self._grism_ready = True

    def init_aperture(self):
        self._aperture_ready = True

    def init_filter(self):
        self._filter_ready = True

    def grism_move_position(self, pos):
        self._grism_move_start = time.perf_counter()

        if pos >= self.MAX_POSITION:
            msg = (
                f"grism position {pos} > maximum allowed={self.MAX_POSITION}\n    "
                f"position modified to {pos} % {self.MAX_POSITION}"
            )
            logger.warning(msg)
            pos = pos % self.MAX_POSITION
        logger.info(f"grism moving to {pos}")
        self._grism_position = pos

    def get_grism_position(self):
        return self._grism_position

    def set_grism_state(self):
        if time.perf_counter() - self._grism_move_start < self.WHEEL_TIME:
            self._grism_ready = False
        else:
            self._grism_ready = True
        return

    def get_grism_state(self):
        self.set_grism_state()
        return self._grism_ready

    def aperture_move_position(self, pos):
        self._aperture_move_start = time.perf_counter()

        if pos >= self.MAX_POSITION:
            msg = (
                f"aperture position {pos} > maximum allowed={self.MAX_POSITION}\n    "
                f"position modified to {pos} % {self.MAX_POSITION}"
            )
            logger.warning(msg)
            pos = pos % self.MAX_POSITION
        logger.info(f"aperture moving to {pos}")
        self._aperture_position = pos

    def get_aperture_position(self):
        return self._aperture_position

    def set_apeture_state(self):
        if time.perf_counter() - self._aperture_move_start < self.WHEEL_TIME:
            self._aperture_ready = False
        else:
            self._aperture_ready = True
        return

    def get_aperture_state(self):
        self.set_apeture_state()
        return self._aperture_ready

    def filter_move_position(self, pos):
        self._filter_move_start = time.perf_counter()

        if pos >= self.MAX_POSITION:
            msg = (
                f"filter position {pos} > maximum allowed={self.MAX_POSITION}\n    "
                f"position modified to {pos} % {self.MAX_POSITION}"
            )
            logger.warning(msg)
            pos = pos % self.MAX_POSITION
        logger.info(f"filter moving to {pos}")
        self._filter_position = pos

    def get_filter_position(self):
        return self._filter_position

    def set_filter_state(self):
        if time.perf_counter() - self._filter_move_start < self.WHEEL_TIME:
            self._filter_ready = False
        else:
            self._filter_ready = True
        return

    def get_filter_state(self):
        self.set_filter_state()
        return self._filter_ready
