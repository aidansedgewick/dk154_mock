# dk154_mock
Mock servers for dk154_control

*still in early dev...*

### Install
You should source the same env you use for `dk154_control`.

`python3 -m pip install -e .`

### Usage

Currently only `Ascol` (TCP) server has mock counterpart.

- Start the mock server: `python3 scripts/start_ascol_mock.py`

- New terminal: run a script that calls `Ascol(test_mode=True)` eg.
    `python3 dk154_control/test_scripts/002_test_status_commands.py --test-mode` 

The 'server' terminal should display what's happening ont the
