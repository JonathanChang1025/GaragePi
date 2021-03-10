# import the necessary packages
from imutils.video import VideoStream
from flask import Flask, Response,render_template, jsonify
import threading
import argparse
import datetime
import imutils
import time
import cv2
import RPi.GPIO as GPIO

# initialize the output frame and a lock used to ensure thread-safe
# exchanges of the output frames (useful when multiple browsers/tabs
# are viewing the stream)
outputFrame = None
lock = threading.Lock()
garageDelay = 10 # minimum delay between door toggles
garageToggled = False # if garage toggle was recently called
garageStart = None # time that garage was called to toggle
# initialize a flask object
app = Flask(__name__)
# initialize GPIO pins
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(8, GPIO.OUT, initial=GPIO.HIGH)
# initialize the video stream and allow the camera sensor to
# warmup
#vs = VideoStream(src=1).start()
cap = cv2.VideoCapture(0)
secondCap = False
cap.set(3, 480)
cap.set(4, 240)
time.sleep(2.0)

@app.route("/")
def index():
    # return the rendered template
    return render_template("index.html")

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

def getSnapshot():
    # grab global references to the video stream, output frame, and
    # lock variables
    global vs, outputFrame, lock, cap, secondCap

    # loop over frames from the video stream
    while True:
        # read the next frame from the video stream, resize it,
        # convert the frame to grayscale, and blur it
        #frame = vs.read()
        if not cap.read()[0]:
            cap.release()
            if secondCap:
                cap = cv2.VideoCapture(0)
                secondCap = False
            else:
                cap = cv2.VideoCapture(1)
                secondCap = True

        _, frame = cap.read()
        frame = imutils.resize(frame, width=640)
        timestamp = datetime.datetime.now()
        cv2.putText(frame, timestamp.strftime("%A %d %B %Y %I:%M:%S%p"), (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

        # acquire the lock, set the output frame, and release the
        # lock
        with lock:
            outputFrame = frame.copy()

def generateVideo():
    # grab global references to the output frame and lock variables
    global outputFrame, lock
    # loop over frames from the output stream
    while True:
        # wait until the lock is acquired
        with lock:
            # check if the output frame is available, otherwise skip
            # the iteration of the loop
            if outputFrame is None:
                continue
            # encode the frame in JPEG format
            (flag, encodedImage) = cv2.imencode(".jpg", outputFrame)
            # ensure the frame was successfully encoded
            if not flag:
                continue
        # yield the output frame in the byte format
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')

@app.route("/video_feed")
def video_feed():
    # return the response generated along with the specific media
    # type (mime type)
    return Response(generateVideo(), mimetype = "multipart/x-mixed-replace; boundary=frame")

def garageTimer():
    global garageDelay, garageToggled

    time.sleep(garageDelay)
    garageToggled = False

    return

@app.route('/toggle_garage')
def toggle_garage():
    global garageToggled, garageDelay, garageStart

    if not garageToggled:
        garageToggled = True
        garageStart = round(time.time())
        # start a thread that will start the timer
        g = threading.Thread(target=garageTimer)
        g.daemon = True
        g.start()

        #print ("Toggled Garage")
        GPIO.output(8, GPIO.LOW) # short the switch
        time.sleep(1)
        GPIO.output(8, GPIO.HIGH) # open circuit the switch
        return jsonify(result="-1")
    else:
        return jsonify(result="{}".format(garageDelay-round(time.time())+garageStart))



# check to see if this is the main thread of execution
if __name__ == '__main__':
    # start a thread that will perform motion detection
    t = threading.Thread(target=getSnapshot)
    t.daemon = True
    t.start()
    # start the flask app
    app.run("0.0.0.0", "5000", debug=True, threaded=True, use_reloader=False)
# release the video stream pointer
#vs.stop()
cap.release()
