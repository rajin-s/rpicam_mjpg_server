# mjpg_server.py
Simple MJPG server for my Pi project

# Usage

`python mjpg_server.py` will start the server in manual mode (mainly for debugging). Once prompted for input, use:

| command | action |
| --- | --- |
| `i` / `idle`        | force the camera into an idle state |
| `c` / `capture`     | manually capture a still image |
| `s` / `stream`      | enable passive video capture |
| `x` / `stop-stream` | disable passive video capture |
| `p` / `print`       | show the camera state as an integer |
| `a`                 | print some output to make sure the script is alive |
| `q` / `quit`        | shut down the server |

Use `--service` to run run without manual input

Use `--debug` to wait for a remote debugger to attach (eg. [VSCode](https://learn.microsoft.com/en-us/visualstudio/python/debugging-python-code-on-remote-linux-machines?view=vs-2022))

# Service Setup

- Use `mjpg_server_service.update.sh` to register with systemd via systemctl so the script runs on boot.
- Use `mjpg_server_service.logs.sh` to view logs via journalctl.
