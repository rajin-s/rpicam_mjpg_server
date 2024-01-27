import sys
import debugpy

if "--debug" in sys.argv:

	debugpy.listen(('0.0.0.0', 5678))
	debugpy.wait_for_client()



import io
from http import server as Server
import socketserver
from threading import Condition as ThreadingCondition, Lock as ThreadingLock, RLock as ThreadingRLock
from time import sleep as Sleep
from datetime import datetime as TimeStamp
from urllib.parse import urlparse as UrlParse
import _thread as thread


import picamera2



Size = (int, int) # tag = sz

g_szStill = (1920, 1080)
g_szVideo = (854, 480)



class CBufferedIOStreamWithCondition(io.BufferedIOBase): # tag = bioswc

	def __init__(self):

		self.m_bufFrame = None
		self.m_tcond = ThreadingCondition()

	def write(self, buf):

		# BB - Is this fully thread safe? (What if another thread is reading a previous part of the buffer?)

		with self.m_tcond:
			self.m_bufFrame = buf
			self.m_tcond.notify_all()



class CAMS:
	Idle 			= 0
	CaptureStill 	= 1
	Stream 			= 2

class CCamera: # tag = cam

	def __init__(
			self,
			szStill: Size,
			szVideo: Size):

		self.m_cams = CAMS.Idle
		self.m_cClientStream = 0
		self.m_trlock = ThreadingRLock()

		# Init camera and configurations

		self.m_picam = picamera2.Picamera2()

		self.m_picamcfgStill = self.m_picam.create_still_configuration(main={ 'size': szStill })
		self.m_picamcfgVideo = self.m_picam.create_video_configuration(main={ 'size': szVideo })

		# For still images, output to a buffer, with an associated lock to something doesn't try to read
		# 	while we're writing the new image

		self.m_bioFrameStill = io.BytesIO()
		self.m_tlockFrameStill = ThreadingLock()
		self.m_tsFrameStill = None

		# For video, output to a buffered stream, with an (internal) associated condition to notify
		# 	clients that there's more data read

		self.m_bioswcStream = CBufferedIOStreamWithCondition()



	def SetCams(self, cams):

		# Must acquire top-level lock in order to change state

		with self.m_trlock:

			if cams == self.m_cams:
				return
			
			# Exit previous state

			match self.m_cams:

				case CAMS.CaptureStill:

					print("stopping still capture mode...", "")

					self.m_picam.stop()
					# Sleep(0.5)

					print ("done")

				case CAMS.Stream:

					print("stopping stream recording... ", "")

					self.m_picam.stop_recording()
					# Sleep(0.5)

					print("done")

			# Enter new state

			self.m_cams = cams

			match self.m_cams:

				case CAMS.Idle:

					print("camera is idling")
				
				case CAMS.CaptureStill:

					print("switching to still capture...")

					self.m_picam.configure(self.m_picamcfgStill)
					self.m_picam.start()

					# Delay after start to give the sensor time to settle

					Sleep(0.5)

					# Acquire lock, rewrite output buffer, and release

					print("capturing still image...")

					with self.m_tlockFrameStill:

						self.m_bioFrameStill.seek(0)
						self.m_picam.capture_file(self.m_bioFrameStill, format='jpeg')

						self.m_tsFrameStill = TimeStamp.now()

					print("finished capture")

				case CAMS.Stream:

					print("switching to video capture...")

					self.m_picam.configure(self.m_picamcfgVideo)

					# Sleep(1.0)

					self.m_picam.start_recording(
									picamera2.encoders.MJPEGEncoder(),
									picamera2.outputs.FileOutput(self.m_bioswcStream))



	def CaptureStillAndResume(self):

		with self.m_trlock:

			self.SetCams(CAMS.CaptureStill)

			if self.m_cClientStream > 0:
				self.SetCams(CAMS.Stream)
			else:
				self.SetCams(CAMS.Idle)

	def AddStreamClient(self):

		with self.m_trlock:

			self.m_cClientStream += 1
			print(f"added stream client, {self.m_cClientStream} total")

			self.SetCams(CAMS.Stream)

	def RemoveStreamClient(self):

		with self.m_trlock:

			self.m_cClientStream -= 1
			print(f"removed stream client, {self.m_cClientStream} remaining")

			if self.m_cClientStream == 0 and self.m_cams == CAMS.Stream:
				self.SetCams(CAMS.Idle)

	def DTSinceLastStillCapture(self):

		with self.m_tlockFrameStill:

			if self.m_tsFrameStill is None:
				return 9999.9

			tsNow = TimeStamp.now()
			dts = tsNow - self.m_tsFrameStill

			return dts.total_seconds()
				
		


g_cam = CCamera(
			szStill=g_szStill,
			szVideo=g_szVideo)



# Set up HTTP server

s_bytesHtmlIndex = \
"""
<html>
	<head>
		<title>Pi MJPG Server</title>
	</head>
	<body>
		<h1>pi-cam-01.local</h1>
		<img src="stream.mjpg" />
		<img src="still.jpg" />
	</body>
</html>
""".encode('utf-8')

class CCameraHttpRequestHandler(Server.BaseHTTPRequestHandler):

	def do_GET(self):

		if self.path == '/':
	
			self.send_response(301)
			self.send_header('Location', '/index.html')
			self.end_headers()
	
		elif self.path == '/index.html':
	
			self.send_response(200)
			self.send_header('Content-Type', 'text/html')
			self.send_header('Content-Length', len(s_bytesHtmlIndex))
			self.end_headers()

			self.wfile.write(s_bytesHtmlIndex)

		elif self.path.startswith('/stream.mjpg'):

			self.RunMjpgStream()

		elif self.path.startswith('/still.jpg'):

			dTRefreshStill = 60

			url = UrlParse(self.path)

			if len(url.query) > 0:

				dTRefreshStill = int(url.query)

				if dTRefreshStill < 1:
					dTRefreshStill = 1

			print(f"getting still image (refresh={dTRefreshStill})...")

			dT = g_cam.DTSinceLastStillCapture()

			if dT > dTRefreshStill:
				g_cam.CaptureStillAndResume()
			else:
				print(f"Reusing still from {dT}s ago...")

			self.send_response(200)
			self.send_header('Content-type', 'image/jpg')
			self.end_headers()

			with g_cam.m_tlockFrameStill:

				buf = g_cam.m_bioFrameStill.getbuffer()

				print(f"writing result capture ({buf.nbytes}B)... ", "")
				self.wfile.write(buf.tobytes())
				print("done")

		elif self.path == '/temp':

			try:
				strTemp = open("/sys/class/thermal/thermal_zone0/temp").read()
				cMiliCelcius = int(strTemp)
				gCelcius = float(cMiliCelcius) / 1000.0

				bytesOutput = f"{gCelcius}".encode('utf-8')

				self.send_response(200)
				self.send_header('Content-Type', 'text/html')
				self.send_header('Content-Length', len(bytesOutput))
				self.end_headers()

				self.wfile.write(bytesOutput)
				
			except:
				self.send_error(404)
				self.end_headers()

		elif self.path == '/favicon.ico':
			pass

		else:

			print(f"unexpected request {self.path}")

			self.send_error(404)
			self.end_headers()
				  

	def RunMjpgStream(self):
			
			self.send_response(200)

			self.send_header('Age', 0)
			self.send_header('Cache-Control', 'no-cache, private')
			self.send_header('Pragma', 'no-cache')
			self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
			self.end_headers()

			g_cam.AddStreamClient()

			dTDelayFrame = 0.25

			url = UrlParse(self.path)

			if len(url.query) > 0:

				cFramePerSecond = int(url.query)
				dTDelayFrame = 1.0 / cFramePerSecond

				if dTDelayFrame < 0.016:
					dTDelayFrame = 0.016

			print(f"requesting video stream (refresh={dTDelayFrame})...")
	  
			try:
				while True:

					with g_cam.m_bioswcStream.m_tcond:
						g_cam.m_bioswcStream.m_tcond.wait()
						
						self.wfile.write(b'--FRAME\r\n')

						self.send_header('Content-Type', 'image/jpeg')
						self.send_header('Content-Length', len(g_cam.m_bioswcStream.m_bufFrame))
						self.end_headers()

						self.wfile.write(g_cam.m_bioswcStream.m_bufFrame)
						self.wfile.write(b'\r\n')

					Sleep(dTDelayFrame)

			except Exception as err:

				print(f"Removed mjpg stream client {self.client_address} :: {err}")

			g_cam.RemoveStreamClient()

class CCameraServer(socketserver.ThreadingMixIn, Server.HTTPServer):
	allow_reuse_address = True
	daemon_threads = True

def RunCameraServer():
	try:
		httpserver = CCameraServer(('', 8088), CCameraHttpRequestHandler)
		httpserver.serve_forever()

	finally:
		print("Server exited")



g_cam.CaptureStillAndResume()



if "--service" in sys.argv:

	RunCameraServer()

else:

	thread.start_new_thread(RunCameraServer, ())

	while True:

		strInput = input("> ")

		if strInput in ["c", "capture"]:
			g_cam.CaptureStillAndResume()

		elif strInput in ["i", "idle"]:
			g_cam.SetCams(CAMS.Idle)

		elif strInput in ["s", "stream"]:
			g_cam.AddStreamClient()

		elif strInput in ["x", "stop-stream"]:
			g_cam.RemoveStreamClient()

		elif strInput in ["p", "print"]:
			print(f"state: {g_cam.m_cams}")

		elif strInput in ["a"]:
			print("alive")

		elif strInput in ["q", "quit"]:
			break



print("Exiting program")