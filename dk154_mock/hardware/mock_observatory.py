from dk154_mock.hardware.mock_telescope import MockTelescope
from dk154_mock.hardware.mock_dfosc import MockDfosc
from dk154_mock.hardware.mock_ccd3 import MockCcd3


class MockDk154:

    def __init__(
        self,
        telescope: MockTelescope = None,
        dfosc: MockDfosc = None,
        ccd3: MockCcd3 = None,
    ):
        """
        A mock observatory for the servers to interact with.

        Parameters

        telescope
        """
        self.telescope = telescope or MockTelescope()
        self.dfosc = dfosc or MockDfosc()
        self.ccd3 = ccd3 or MockCcd3()

    @classmethod
    def start_ready(cls):
        tel = MockTelescope.start_in_ready_state()
        dfosc = MockDfosc.start_in_ready_state()
        return cls(telescope=tel, dfosc=dfosc)
