#!/usr/bin/env python
import cv2
import time
import logging as log
import sys
import math

from openvino.inference_engine import IENetwork, IEPlugin
from imutils.video import FPS

class Vision:
    def __init__(self, model_xml, model_bin, is_headless, is_async_mode, confidence_interval):
        log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)

        self.is_headless = is_headless
        self.is_async_mode = is_async_mode
        self.confidence_interval = confidence_interval

        # Get executable network and its parameters
        ((self.n, self.c, self.h, self.w), 
         self.input_blob, 
         self.out_blob, 
         self.exec_net) = self.get_executable_network(model_xml,model_bin)

        # Initialize VideoCapture and let it warm up
        self.cap = cv2.VideoCapture(0)
        time.sleep(1)

        # Initialize FPS counter
        self.fps = FPS()

        # Used to provide OpenCV rendering time
        self.render_time = 0

    def start(self):
        """ Perform inference in synchronous or asynchronous mode while capturing
        frames using VideoCapture object. """
        self.fps.start()

        log.info("Starting video stream. Press ESC to stop.")

        ret, frame = self.cap.read()

        # Async request identifiers
        cur_request_id = 0
        next_request_id = 1

        # Get resolution of video capture.
        self.initial_w = self.cap.get(3)
        self.initial_h = self.cap.get(4)

        while self.cap.isOpened():
            try:
                self.fps.update()

                if self.is_async_mode:
                    ret, next_frame = self.cap.read()
                else:
                    ret, frame = self.cap.read()
                if not ret:
                    break

                # Main synchronization point. Start the next inference request,
                # while waiting for the current one to complete.
                inf_start = time.time()

                if self.is_async_mode:
                    # Resize, change layout, reshape to fit network input size and
                    # start asynchronous inference
                    in_frame = self.prep_frame(next_frame)
                    self.exec_net.start_async(request_id=next_request_id, inputs={self.input_blob: in_frame})
                else:
                    # Resize, change layout, reshape to fit network input size and
                    # start synchronous inference
                    in_frame = self.prep_frame(frame)
                    self.exec_net.start_async(request_id=cur_request_id, inputs={self.input_blob: in_frame})
                if self.exec_net.requests[cur_request_id].wait(-1) == 0:
                    # Capture inference times for synchronous inference
                    inf_end = time.time()
                    det_time = inf_end - inf_start
                    
                # Parse detection results of the current request.
                res = self.exec_net.requests[cur_request_id].outputs[self.out_blob]

                for pred in res[0][0]:
                    if self.check_probability(pred[2]):
                        self.process_prediction(pred,frame)

                if not self.is_headless:
                    self.display_frame(frame)

                # Swap async request identifiers
                if self.is_async_mode:
                    cur_request_id, next_request_id = next_request_id, cur_request_id
                    frame = next_frame

                # Enable key detection in output window.
                key = cv2.waitKey(1)

                # Check if ESC has been pressed.
                if key == 27:
                    self.cleanup()
                    break

            # Catch ctrl+c while in headless mode.
            except KeyboardInterrupt:
                self.cleanup()
                break

    def get_executable_network(self, model_xml, model_bin):
        """ Initialize MYRIAD X VPU with executable network and return network 
        layout, IO blobs and reference to network """
        
        # Initialize plugin
        log.info("Initializing plugin for MYRIAD X VPU.")
        plugin = IEPlugin(device='MYRIAD')
        
        # Initialize network
        log.info("Reading Intermediate Representation.")
        net = IENetwork(model=model_xml, weights=model_bin)
                
        # Initialize IO blobs
        input_blob = next(iter(net.inputs))
        out_blob = next(iter(net.outputs))

        # Load network into IE plugin
        log.info("Loading Intermediate Representation of {0}.".format(net.name))
        exec_net = plugin.load(network=net, num_requests=2)
        
        # Get input parameters of network
        n, c, h, w = net.inputs[input_blob].shape
        
        return ((n, c, h, w), input_blob, out_blob, exec_net)

    def prep_frame(self, frame):
        """ Prepare frame for inference - resize, transpose and reshape to
        fit network layout """
        
        in_frame = cv2.resize(frame, (self.w, self.h))
        in_frame = in_frame.transpose((2, 0, 1))  # Change data layout from HWC to CHW
        in_frame = in_frame.reshape((self.n, self.c, self.h, self.w))
        
        return in_frame

    def check_probability(self, prob):
        """ Check if probability is well formed and if it is greater than our
        confidence interval """
        return not math.isnan(prob) and prob > self.confidence_interval and  prob <= 1

    def process_prediction(self, pred, frame):
        """ Extract bounding box coordinates of our prediction, get class label,
        print info to stdout and draw data on the frame if specified. Returns
        class label, probability of that label and bbox coordinates. """
        pred_boxpts = ((int(pred[3] * self.initial_w), int(pred[4] * self.initial_h)),
                       (int(pred[5] * self.initial_w), int(pred[6] * self.initial_h)))

        class_id = int(pred[1])

        label = 'Plant' if class_id == 16 else 'Obstacle'

        log.info("Prediction: {0}, confidence={1}, boxpoints={2}"
            .format(label, pred[2], pred_boxpts))

        if not self.is_headless:
            self.draw_data(frame, pred_boxpts, class_id, label, pred[2])

        return (label,pred[2],pred_boxpts)


    def display_frame(self, frame):
        render_start = time.time()

        cv2.imshow("Detection Results", frame)

        render_end = time.time()
        self.render_time = render_end - render_start

    def draw_data(self, frame, pred_boxpts, class_id, label, prob):
        """ Draw bounding box, class label and its probability on the frame """
        # Draw box and label\class_id
        color = (0,255,0) if class_id == 16 else (0,0,255)
        cv2.rectangle(frame, pred_boxpts[0], pred_boxpts[1], color, 2)
        cv2.putText(frame, label + ' ' + str(round(prob * 100, 1)) + ' %', (pred_boxpts[0][0], pred_boxpts[0][1] - 7), cv2.FONT_HERSHEY_COMPLEX, 0.6, color, 1)
        #cv2.putText(frame, "OpenCV rendering time: {:.3f} ms".format(self.render_time * 1000), (15, 15), cv2.FONT_HERSHEY_COMPLEX, 0.5, (10, 10, 200), 1)
        #cv2.putText(frame, "GrowBot Vision System", (15, 30), cv2.FONT_HERSHEY_COMPLEX, 0.5, (10, 10, 200), 1)


    def cleanup(self):
        """ Release resources and close any windows. """
        self.cap.release()

        if not self.is_headless:
            cv2.destroyAllWindows()

        self.fps.stop()

def main():
    # Hardcoded models
    model_xml = '/home/pi/ssd300.xml'
    model_bin = '/home/pi/ssd300.bin'

    vision = Vision(model_xml,
                    model_bin,
                    is_headless=False,
                    is_async_mode=True,
                    confidence_interval=0.5)
    vision.start()

    log.info("Approx FPS: {:.2f}".format(vision.fps.fps()))

if __name__ == "__main__":
    main()
