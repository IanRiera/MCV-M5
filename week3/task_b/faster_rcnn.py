import sys, os, cv2
import torch
assert torch.__version__.startswith("1.7")   # need to manually install torch 1.8 if Colab changes its default version
from detectron2.utils.logger import setup_logger
setup_logger()

# import some common detectron2 utilities
from detectron2 import model_zoo
from detectron2.engine import DefaultPredictor
from detectron2.config import get_cfg
from detectron2.utils.visualizer import Visualizer
from detectron2.data import MetadataCatalog, DatasetCatalog

import argparse

def parse_args(args=sys.argv[1:]):
    parser = argparse.ArgumentParser()

    parser.add_argument('--model', type=str, default='faster_rcnn_X_101_32x8d_FPN_3x',
                        help='pre-trained Faster R-CNN model to run inference on KITTI-MOTS dataset')

    parser.add_argument('--seq', type=str, default='0000',
                        help='sequence of KITTI-MOTS training set to run inference on')

    return parser.parse_args(args)

if __name__ == '__main__':
    args = parse_args()

    model_path = 'COCO-Detection/' + args.model + '.yaml'
    print(model_path)
    
    # Run a pre-trained detectron2 model
    cfg = get_cfg()

    cfg.merge_from_file(model_zoo.get_config_file(model_path))
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5  # set threshold for this model

    cfg.MODEL.WEIGHTS = model_zoo.get_checkpoint_url(model_path)
    predictor = DefaultPredictor(cfg)

    results_dir = '/home/group02/week3/results/task_b/'
    data_path = '/home/group02/mcv/datasets/KITTI-MOTS/training/image_02/' + args.seq

    cfg.OUTPUT_DIR = results_dir + args.model + '/' + args.seq

    for subdir, dirs, files in os.walk(data_path):
        os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
        for file in files:
            input_path = os.path.join(subdir, file)
            output_path = os.path.join(cfg.OUTPUT_DIR, file)

            im = cv2.imread(input_path)

            outputs = predictor(im)

            # print(outputs["instances"].pred_classes)
            # print(outputs["instances"].pred_boxes)

            # We can use `Visualizer` to draw the predictions on the image.
            v = Visualizer(im[:, :, ::-1], MetadataCatalog.get(cfg.DATASETS.TRAIN[0]), scale=1.2)
            out = v.draw_instance_predictions(outputs["instances"].to("cpu"))
            cv2.imwrite(output_path, out.get_image()[:, :, ::-1])
