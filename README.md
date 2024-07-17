# dk154_mock
Mock servers for dk154_control.

### Install
You should source the same env you use for `dk154_control`.

Clone this repo.

Install in developer mode:
 - `python3 -m pip install -e .`

### Usage

Mock servers available for `ASCOL` (the TCS), `DFOSC` and `CCD3` (DFOSC camera).

- Start the mock servers: `python3 scripts/start_mock_servers.py`


In your scripts which use the `dk154_control` classes, you will need to use
eg. `Ascol(test_mode=True)` , `Dfosc(test_mode=True` and `Ccd3(test_mode=True)`
to connect to the mock servers instead of trying to connect to La Silla.


Note: the mock servers run on `localhost:8883`, `localhost:8888` and `localhost:8889`.
The `test_mode` flag switches to these locations.


