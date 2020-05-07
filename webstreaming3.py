# USAGE
# python webstreaming.py --ip 0.0.0.0 --port 8000

# import the necessary packages
from pyimagesearch.motion_detection import SingleMotionDetector
from imutils.video import VideoStream
from flask import Response
from flask import Flask
from flask import render_template
import threading
import argparse
import datetime
import imutils
import time
import cv2

# initialize the output frame and a lock used to ensure thread-safe
# exchanges of the output frames (useful for multiple browsers/tabs
# are viewing tthe stream)
outputFrame0 = None
outputFrame1 = None
lock0 = threading.Lock()
lock1 = threading.Lock()

# initialize a flask object
app = Flask(__name__)

# initialize the video stream and allow the camera sensor to
# warmup
#vs = VideoStream(usePiCamera=1).start()
vs0 = VideoStream(src=0).start()
vs1 = VideoStream(src=1).start()
time.sleep(2.0)

@app.route("/")
def index():
	# return the rendered template
	return render_template("index.html")

def detect_motion(frameCount):
	# grab global references to the video stream, output frame, and
	# lock variables
	global vs, outputFrame0, outputFrame1, lock0, lock1

	# initialize the motion detector and the total number of frames
	# read thus far
	md0 = SingleMotionDetector(accumWeight=0.1)
	md1 = SingleMotionDetector(accumWeight=0.1)
	total = 0

	# loop over frames from the video stream
	while True:
		# read the next frame from the video stream, resize it,
		# convert the frame to grayscale, and blur it
		frame0 = vs0.read()
		frame0 = imutils.resize(frame0, width=400)
		gray0 = cv2.cvtColor(frame0, cv2.COLOR_BGR2GRAY)
		gray0 = cv2.GaussianBlur(gray0, (7, 7), 0)
		frame1 = vs1.read()
		frame1 = imutils.resize(frame1, width=400)
		gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
		gray1 = cv2.GaussianBlur(gray1, (7, 7), 0)

		# grab the current timestamp and draw it on the frame
		timestamp = datetime.datetime.now()
		'''cv2.putText(frame, timestamp.strftime(
			"%A %d %B %Y %I:%M:%S%p"), (10, frame.shape[0] - 10),
			cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)
		'''
		# if the total number of frames has reached a sufficient
		# number to construct a reasonable background model, then
		# continue to process the frame
		if total > frameCount:
			# detect motion in the image
			motion0 = md.detect(gray0)
			motion1 = md.detect(gray1)

			# cehck to see if motion was found in the frame
			if motion0 is not None:
				# unpack the tuple and draw the box surrounding the
				# "motion area" on the output frame
				(thresh, (minX, minY, maxX, maxY)) = motion0
				cv2.rectangle(frame, (minX, minY), (maxX, maxY),
					(0, 0, 255), 2)
			if motion1 is not None:
				# unpack the tuple and draw the box surrounding the
				# "motion area" on the output frame
				(thresh, (minX, minY, maxX, maxY)) = motion1
				cv2.rectangle(frame, (minX, minY), (maxX, maxY),
					(0, 0, 255), 2)
		
		# update the background model and increment the total number
		# of frames read thus far
		md0.update(gray0)
		md1.update(gray1)
		total += 1

		# acquire the lock, set the output frame, and release the
		# lock
		with lock0:
			outputFrame0 = frame0.copy()
		with lock1:
			outputFrame1 = frame1.copy()
		
def generate():
	global outputFrame0, outputFrame1, lock0, lock1
	while True:
		with lock0:
			if outputFrame0 is None:
				continue
			(flag0, encodedImage0) = cv2.imencode(".jpg", outputFrame0)
			if not flag0:
				continue
		yield(b'--frame0\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
			bytearray(encodedImage0) + b'\r\n')
		with lock1:
			if outputFrame1 is None:
				continue
			(flag1, encodedImage1) = cv2.imencode(".jpg", outputFrame1)
			if not flag1:
				continue
		yield(b'--frame1\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
			bytearray(encodedImage1) + b'\r\n')

@app.route("/video_feed")
def video_feed():
	# return the response generated along with the specific media
	# type (mime type)
	return Response(generate(),
		mimetype = "multipart/x-mixed-replace; boundary=frame0")

# check to see if this is the main thread of execution
if __name__ == '__main__':
	# construct the argument parser and parse command line arguments
	ap = argparse.ArgumentParser()
	ap.add_argument("-i", "--ip", type=str, required=True,
		help="ip address of the device")
	ap.add_argument("-o", "--port", type=int, required=True,
		help="ephemeral port number of the server (1024 to 65535)")
	ap.add_argument("-f", "--frame-count", type=int, default=32,
		help="# of frames used to construct the background model")
	args = vars(ap.parse_args())

	# start a thread that will perform motion detection
	t = threading.Thread(target=detect_motion, args=(
		args["frame_count"],))
	t.daemon = True
	t.start()

	# start the flask app
	app.run(host=args["ip"], port=args["port"], debug=True,
		threaded=True, use_reloader=False)

# release the video stream pointer
vs0.stop()
vs1.stop()