from openvino.inference_engine import IENetwork, IEPlugin
from imutils.video import FPS
from math import exp as exp

import logging as log
import sys
import cv2
import time


class YoloV3Params:
    def __init__(self, param, side):
        """
        Constructor for YoloV3 parameters.
        :param param:
        :param side:
        """
        self.num = 3 if 'num' not in param else len(param['mask'].split(',')) if 'mask' in param else int(param['num'])
        self.coords = 4 if 'coords' not in param else int(param['coords'])
        self.classes = 80 if 'classes' not in param else int(param['classes'])
        self.anchors = [10.0, 13.0, 16.0, 30.0, 33.0, 23.0, 30.0, 61.0, 62.0, 45.0, 59.0, 119.0, 116.0, 90.0, 156.0,
                        198.0,
                        373.0, 326.0] if 'anchors' not in param else [float(a) for a in param['anchors'].split(',')]
        self.side = side

        if self.side == 13:
            self.anchor_offset = 2 * 6
        elif self.side == 26:
            self.anchor_offset = 2 * 3
        elif self.side == 52:
            self.anchor_offset = 2 * 0
        else:
            assert False, "Invalid output size. Only 13, 26 and 52 sizes are supported for output spatial dimensions"


def entry_index(side, coord, classes, location, entry):
    """
    Compute entry index of single entry.
    :param side:
    :param coord:
    :param classes:
    :param location:
    :param entry:
    :return:
    """
    side_power_2 = side ** 2
    n = location // side_power_2
    loc = location % side_power_2

    return int(side_power_2 * (n * (coord + classes + 1) + entry) + loc)


def scale_bbox(x, y, h, w, class_id, confidence, h_scale, w_scale):
    """
    Scale bounding box to fit on the frame.
    :param x:           X coordinate
    :param y:           Y coordinate
    :param h:           Height of the bbox
    :param w:           Width of the bbox
    :param class_id:    Class label
    :param confidence:  Prediction probability
    :param h_scale:     Height scaling factor
    :param w_scale:     Width scaling factor
    :return:            Dictionary with scaled coordinates of the bounding box
    """
    xmin = int((x - w / 2) * w_scale)
    ymin = int((y - h / 2) * h_scale)
    xmax = int(xmin + w * w_scale)
    ymax = int(ymin + h * h_scale)

    return dict(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax, class_id=class_id, confidence=confidence)


def parse_yolo_region(blob, resized_image_shape, original_im_shape, params, threshold):
    """
    Parse Yolo regions.
    :param blob:
    :param resized_image_shape:
    :param original_im_shape:
    :param params:
    :param threshold:
    :return:
    """
    # Extract layer parameters
    orig_im_h, orig_im_w = original_im_shape
    resized_image_h, resized_image_w = resized_image_shape
    objects = list()
    predictions = blob.flatten()
    side_square = params.side * params.side

    # Parse YOLO Region output
    for i in range(side_square):
        row = i // params.side
        col = i % params.side
        for n in range(params.num):
            obj_index = entry_index(params.side, params.coords, params.classes, n * side_square + i, params.coords)
            scale = predictions[obj_index]
            if scale < threshold:
                continue
            box_index = entry_index(params.side, params.coords, params.classes, n * side_square + i, 0)
            x = (col + predictions[box_index + 0 * side_square]) / params.side * resized_image_w
            y = (row + predictions[box_index + 1 * side_square]) / params.side * resized_image_h

            # Capture overflows caused by exp
            try:
                w_exp = exp(predictions[box_index + 2 * side_square])
                h_exp = exp(predictions[box_index + 3 * side_square])
            except OverflowError:
                continue
            w = w_exp * params.anchors[params.anchor_offset + 2 * n]
            h = h_exp * params.anchors[params.anchor_offset + 2 * n + 1]
            for j in range(params.classes):
                class_index = entry_index(params.side, params.coords, params.classes, n * side_square + i,
                                          params.coords + 1 + j)
                confidence = scale * predictions[class_index]
                if confidence < threshold:
                    continue
                objects.append(scale_bbox(x=x, y=y, h=h, w=w, class_id=j, confidence=confidence,
                                          h_scale=orig_im_h / resized_image_h, w_scale=orig_im_w / resized_image_w))
    return objects


def intersection_over_union(bbox_a, bbox_b):
    """
    Compute intersection over union as an evaluation metric.
    :param bbox_a:   First bounding box
    :param bbox_b:   Second bounding box
    :return:        Intersection over union ratio
    """
    width_of_overlap_area = min(bbox_a["xmax"], bbox_b["xmax"]) - max(bbox_a["xmin"], bbox_b["xmin"])
    height_of_overlap_area = min(bbox_a["ymax"], bbox_b["ymax"]) - max(bbox_a["ymin"], bbox_b["ymin"])

    if width_of_overlap_area < 0 or height_of_overlap_area < 0:
        area_of_overlap = 0
    else:
        area_of_overlap = width_of_overlap_area * height_of_overlap_area

    box_1_area = (bbox_a["ymax"] - bbox_a["ymin"]) * (bbox_a["xmax"] - bbox_a["xmin"])
    box_2_area = (bbox_b["ymax"] - bbox_b["ymin"]) * (bbox_b["xmax"] - bbox_b["xmin"])

    area_of_union = box_1_area + box_2_area - area_of_overlap

    if area_of_union == 0:
        return 0

    return area_of_overlap / area_of_union


class Vision:
    """
    Implementation of the computer vision system for GrowBot using YoloV3 DNN. This implementation allows for inference
    to be executed on MYRIAD X VPU only.
    """
    output_str = "Prediction: {:^9}, Confidence: {:10f}, Boxpoints: (({:4}, {:4}),({:4}), ({:4}))"

    def __init__(self, prob_threshold=0.5, iou_threshold=0.4, is_headless=True):
        """
        Constructor for the Vision class.
        :param prob_threshold:  Confidence interval
        :param iou_threshold:   Intersection over union threshold
        :param is_headless:     If true, system will operate in headless mode, otherwise the frames will be displayed
                                on the screen
        """
        log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)

        self.is_headless = is_headless
        self.prob_threshold = prob_threshold
        self.iou_threshold = iou_threshold

        # Intermediate Representation files
        self.model_xml = "frozen_yolo_v3.xml"
        self.model_bin = "frozen_yolo_v3.bin"
        self.model_labels = "frozen_yolo_v3.labels"

        # Get executable network with parameters
        (self.n, self.c, self.h, self.w), self.input_blob, self.exec_net, self.net = \
            self.get_executable_network(self.model_xml, self.model_bin)

        # Set default batch_size to 1
        self.net.batch_size = 1

        # Read labels
        with open(self.model_labels, 'r') as f:
            self.labels_map = [x.strip() for x in f]

        self.is_async_mode = True

        self.fps = FPS()

        self.cap = cv2.VideoCapture(0)
        time.sleep(1)

        self.render_time = 0
        self.parsing_time = 0
        self.infr_time = 0

    @staticmethod
    def get_executable_network(model_xml, model_bin):
        """
        Generate executable network and retrieve network IO parameters needed for inference.
        :param model_xml:   Intermediate representation of the network
        :param model_bin:   Intermediate representation of the network weights
        :return:            Network IO parameters and network with its executable
        """

        # Initialize plugin
        log.info("Initializing plugin for MYRIAD X VPU.")
        plugin = IEPlugin(device="MYRIAD")

        # Initialize network
        log.info("Reading Intermediate Representation.")
        net = IENetwork(model=model_xml, weights=model_bin)

        # Initialize IO blobs
        input_blob = next(iter(net.inputs))

        # Load network into IE plugin
        log.info("Loading Intermediate Representation of {0}.".format(net.name))
        exec_net = plugin.load(network=net, num_requests=2)

        # Get input parameters of the network
        n, c, h, w = net.inputs[input_blob].shape

        return (n, c, h, w), input_blob, exec_net, net

    def start(self):
        """
        Start inference procedure. This starts an infinite loop over frames captured using PiCamera. Press ctrl+c to
        stop in headless mode, otherwise press ESC key.
        :return:
        """
        ret, frame = self.cap.read()

        cur_request_id = 0
        next_request_id = 1

        self.fps.start()

        log.info("Starting video stream. Press ESC to stop.")

        # Loop over frames captured by VideoCapture until stopped by user
        while self.cap.isOpened():
            try:
                self.fps.update()

                # First asynchronous point. In the asynchronous mode, capture frame to populate the next inference
                # request. In the synchronous mode, we capture frame to the current inference request
                if self.is_async_mode:
                    ret, next_frame = self.cap.read()
                else:
                    ret, frame = self.cap.read()
                if not ret:
                    break

                if self.is_async_mode:
                    request_id = next_request_id
                    in_frame = cv2.resize(next_frame, (self.w, self.h))
                else:
                    request_id = cur_request_id
                    in_frame = cv2.resize(frame, (self.w, self.h))

                # resize input_frame to network size
                in_frame = in_frame.transpose((2, 0, 1))  # Change data layout from HWC to CHW
                in_frame = in_frame.reshape((self.n, self.c, self.h, self.w))

                # Start inference
                self.exec_net.start_async(request_id=request_id, inputs={self.input_blob: in_frame})

                # Collect object detection results and measure parsing time
                objects = list()
                if self.exec_net.requests[cur_request_id].wait(-1) == 0:
                    output = self.exec_net.requests[cur_request_id].outputs

                    start_time = time.time()
                    for layer_name, out_blob in output.items():
                        layer_params = YoloV3Params(self.net.layers[layer_name].params, out_blob.shape[2])
                        objects += parse_yolo_region(out_blob, in_frame.shape[2:], frame.shape[:-1], layer_params, self.prob_threshold)

                # Filter overlapping boxes with respect to the iou_threshold parameter
                for i in range(len(objects)):
                    if objects[i]["confidence"] == 0:
                        continue

                    for j in range(i + 1, len(objects)):
                        if intersection_over_union(objects[i], objects[j]) > self.iou_threshold:
                            objects[j]["confidence"] = 0

                # Filter objects with respect to the prob_threshold parameter
                objects = [obj for obj in objects if obj["confidence"] >= self.prob_threshold]

                origin_im_size = frame.shape[:-1]
                for pred in objects:
                    # Validation bbox of detected object
                    if pred["xmax"] > origin_im_size[0] or pred["ymax"] > origin_im_size[0] or pred["xmin"] < 0 or pred["ymin"] < 0:
                        continue

                    det_label = self.labels_map[pred["class_id"]] \
                        if self.labels_map and len(self.labels_map) >= pred["class_id"] \
                        else str(pred['class_id'])

                    log.info(self.output_str.format(det_label, pred["confidence"], pred["xmin"], pred["ymin"], pred["xmax"], pred["ymax"]))

                    if not self.is_headless:
                        self.draw_bbox(frame, det_label, pred)

                if not self.is_headless:
                    cv2.imshow("DetectionResults", frame)

                if self.is_async_mode:
                    cur_request_id, next_request_id = next_request_id, cur_request_id
                    frame = next_frame

                key = cv2.waitKey(1)

                # Capture ESC key
                if key == 27:
                    self.cleanup()
                    break

            # Catch ctrl+c while in headless mode.
            except KeyboardInterrupt:
                self.cleanup()
                break


    @staticmethod
    def draw_bbox(frame, det_label, pred):
        """
        Draw bounding box on the frame.
        :param frame:       frame used for inference
        :param det_label:   prediction label
        :param pred:        prediction details
        :return:
        """
        # Set bounding box color to green if plant, otherwise set to red
        color = (0, 255, 0) if pred["class_id"] == 59 else (0, 0, 255)

        cv2.rectangle(frame, (pred["xmin"], pred["ymin"]), (pred["xmax"], pred["ymax"]), color, 2)
        cv2.putText(frame,
                    det_label + ' ' + str(round(pred["confidence"] * 100, 1)) + ' %',
                    (pred["xmin"], pred["ymin"] - 7), cv2.FONT_HERSHEY_COMPLEX, 0.6, color, 1)

    def cleanup(self):
        """
        Release resources and close any windows if open
        :return:
        """
        self.cap.release()

        if not self.is_headless:
            cv2.destroyAllWindows()

        self.fps.stop()
        log.info("Approx FPS: {:.5f}".format(self.fps.fps()))


def main():
    vision = Vision(is_headless=False)
    vision.start()


if __name__ == "__main__":
    main()
