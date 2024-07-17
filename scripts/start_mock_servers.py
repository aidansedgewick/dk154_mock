"""
Start instances of the MockAscol and MockDfosc servers.
These are controlled with the Ascol() and Dfosc() classes in `dk154_control`

26-06-2024
"""

import threading
import yaml
from argparse import ArgumentParser
from pathlib import Path

from dk154_mock.controls import MockAscolServer, MockDfoscServer, get_mock_ccd3_server
from dk154_mock.hardware import MockDk154

if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("-c", "--config", default=None, type=Path)
    parser.add_argument("-d", "--data-path", default=None, type=Path)
    parser.add_argument("-w", "--no-data", default=False, action="store_true")

    args = parser.parse_args()

    if args.config is None:
        ascol_kwargs = {}
        ccd3_kwargs = {"data_path": args.data_path}
        dfosc_kwargs = {}
    else:
        with open(args.config) as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
        ascol_kwargs = config.get("ascol", {})
        ccd3_kwargs = config.get("ccd3", {})
        dfosc_kwargs = config.get("dfosc", {})

    mock_dk154 = MockDk154()  # Mock observatory that the servers inter

    ascol_server = MockAscolServer(obs=mock_dk154, **ascol_kwargs)
    ascol_server_thread = threading.Thread(target=ascol_server.start, daemon=False)

    dfosc_server = MockDfoscServer(obs=mock_dk154, **dfosc_kwargs)
    dfosc_server_thread = threading.Thread(target=dfosc_server.start, daemon=False)

    ccd3_server = get_mock_ccd3_server(mock_dk154)

    ascol_server_thread.start()
    dfosc_server_thread.start()
    ccd3_server.serve_forever()
