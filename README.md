# mjpg_server.py
A simple MJPG server for my Pi project

Adapted from the [picamera2 docs example server](https://github.com/raspberrypi/picamera2/blob/main/examples/mjpeg_server.py)

# Usage

`python mjpg_server.py` will start the server in manual mode (mainly for debugging). Once prompted for input, use:

| command 				| action 												|
| --------------------- | ----------------------------------------------------- |
| `i` / `idle`			| force the camera into an idle state 					|
| `c` / `capture`		| manually capture a still image 						|
| `s` / `stream`		| enable passive video capture 							|
| `x` / `stop-stream`	| disable passive video capture 						|
| `p` / `print`			| show the camera state as an integer 					|
| `a`					| print some output to make sure the script is alive 	|
| `q` / `quit`			| shut down the server 									|

Use `--service` to run run without manual input

Use `--debug` to wait for a remote debugger to attach (eg. [VSCode](https://learn.microsoft.com/en-us/visualstudio/python/debugging-python-code-on-remote-linux-machines?view=vs-2022))

Serves over HTTP on port 8088

- `/stream.mjpg` -- low-res mjpg video feed, single query param can be used to indicate the desired frame rate (eg. `/stream.mjpg?30`, default is 4 fps)
- `/still.jpg` -- high-res still image, single query param can be used to indicate how recent the image must be (eg. `/still.jpg?1`, default is 30s). The first request will capture the image, subsequent requests will reuse the same cached image
- `/temp` -- reads CPU temperature for monitoring
- `/`, `/index.html` -- test page

# Service Setup

- Use `mjpg_server_service.update.sh` to register with systemd via systemctl so the script runs on boot.
- Use `mjpg_server_service.logs.sh` to view logs via journalctl.
