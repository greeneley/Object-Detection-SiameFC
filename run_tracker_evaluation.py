from __future__ import division
import sys
import os
import numpy as np
from PIL import Image
import src.siamese as siam
from src.tracker import tracker
from src.parse_arguments import parse_arguments
from src.region_to_bbox import region_to_bbox
from PIL import Image
import time
from os.path import isfile, join
import cv2
"""
    tracking procedure:
    1,input a image sequence of a vedio
    2,z = first frame
    3,x = next img
    4,pad and crop z,x, generate three version of diffenrent scale(crop to different size and rescale to a certain size)
    5,calculate score map * 3
    6,fetch the max score and update size(for step 4)(scale)
    7,cosine window
    8,update pos_x, pos_y
    9,z = x, with new size, pos_x, pos_y
    10,goto step 3

"""
import glob
import os
for f in glob.glob("./result/*.png"):
    os.remove(f)


def evaluate():
    # avoid printing TF debugging information
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    # TODO: allow parameters from command line or leave everything in json files?
    hp, evaluation, run, env, design = parse_arguments()
    # Set size for use with tf.image.resize_images with align_corners=True.
    # For example,
    #   [1 4 7] =>   [1 2 3 4 5 6 7]    (length 3*(3-1)+1)
    # instead of
    # [1 4 7] => [1 1 2 3 4 5 6 7 7]  (length 3*3)
    final_score_sz = hp.response_up * (design.score_sz - 1) + 1

    # build the computational graph of Siamese fully-convolutional network
    siamNet = siam.Siamese(batch_size=1)
    # get tensors that will be used during tracking
    image, z_crops, x_crops, templates_z, scores, loss, _, distance_to_gt, summary = siamNet.build_tracking_graph_train(
        final_score_sz, design, env, hp)
    # iterate through all videos of evaluation.dataset
    if evaluation.video == 'all':
        dataset_folder = os.path.join(env.root_dataset, evaluation.dataset)
        videos_list = [v for v in os.listdir(dataset_folder)]
        videos_list.sort()
        nv = np.size(videos_list)
        speed = np.zeros(nv)
        precisions = np.zeros(nv)
        precisions_auc = np.zeros(nv)
        ious = np.zeros(nv)
        lengths = np.zeros(nv)
        for i in range(nv):
            gt, frame_name_list, frame_sz, n_frames = _init_video(
                env, evaluation, videos_list[i])

            gt_ = gt[0:, :]
            frame_name_list_ = frame_name_list[0:]
            # coordinate of gt is the bottom left point of the bbox
            pos_x, pos_y, target_w, target_h = region_to_bbox(gt_[0])
            idx = i
            bboxes, speed[idx] = tracker(hp, run, design, frame_name_list, pos_x, pos_y, target_w, target_h, final_score_sz,
                                         image, templates_z, scores, path_ckpt=os.path.join(design.saver_folder, design.path_ckpt), siamNet=siamNet)
            lengths[idx], precisions[idx], precisions_auc[idx], ious[idx] = _compile_results(
                gt_, bboxes, evaluation.dist_threshold)
            print(str(i) + ' -- ' + videos_list[i] +
                  ' -- Precision: ' + "%.2f" % precisions[idx] +
                  ' -- Precisions AUC: ' + "%.2f" % precisions_auc[idx] +
                  ' -- IOU: ' + "%.2f" % ious[idx] +
                  ' -- Speed: ' + "%.2f" % speed[idx] + ' --')

        tot_frames = np.sum(lengths)
        mean_precision = np.sum(precisions * lengths) / tot_frames
        mean_precision_auc = np.sum(precisions_auc * lengths) / tot_frames
        mean_iou = np.sum(ious * lengths) / tot_frames
        mean_speed = np.sum(speed * lengths) / tot_frames
        print('-- Overall stats (averaged per frame) on ' +
              str(nv) + ' videos (' + str(tot_frames) + ' frames) --')
        print(' -- Precision ' + "(%d px)" % evaluation.dist_threshold + ': ' + "%.2f" % mean_precision +
              ' -- Precisions AUC: ' + "%.2f" % mean_precision_auc +
              ' -- IOU: ' + "%.2f" % mean_iou +
              ' -- Speed: ' + "%.2f" % mean_speed + ' --')
    # evaluate only one vedio
    else:
        gt, frame_name_list, frame_sz, n_frames = _init_video(
            env, evaluation, evaluation.video)
        pos_x, pos_y, target_w, target_h = region_to_bbox(gt[0])
        bboxes, speed = tracker(hp, run, design, frame_name_list, pos_x, pos_y, target_w, target_h, final_score_sz,
                                image, templates_z, scores, path_ckpt=os.path.join(design.saver_folder, design.path_ckpt), siamNet=siamNet)
        _, precision, precision_auc, iou, robustness = _compile_results(
            gt, bboxes, evaluation.dist_threshold)

        print(evaluation.video +
              ' -- Precision ' + "(%d px)" % evaluation.dist_threshold + ': ' + "%.2f" % precision +
              ' -- Precision AUC: ' + "%.2f" % precision_auc +
              ' -- IOU: ' + "%.2f" % iou +
              ' -- Robustness: ' + "%.2f" % robustness +
              ' -- Speed: ' + "%.2f" % speed + ' --')
        return precision, precision_auc, iou, speed


def _compile_results(gt, bboxes, dist_threshold):
    l = np.size(bboxes, 0)
    gt4 = np.zeros((l, 4))
    new_distances = np.zeros(l)
    new_ious = np.zeros(l)
    n_thresholds = 50
    precisions_ths = np.zeros(n_thresholds)
    robustness = 0
    for i in range(l):
        gt4[i, :] = region_to_bbox(gt[i, :], center=False)
        new_distances[i] = _compute_distance(bboxes[i, :], gt4[i, :])
        new_ious[i] = _compute_iou(bboxes[i, :], gt4[i, :])
        if(new_ious[i] == 0.0):
            robustness += 1

    # what's the percentage of frame in which center displacement is inferior to given threshold? (OTB metric)
    precision = sum(new_distances < dist_threshold) / \
        np.size(new_distances) * 100

    # find above result for many thresholds, then report the AUC
    thresholds = np.linspace(0, 25, n_thresholds+1)
    thresholds = thresholds[-n_thresholds:]
    # reverse it so that higher values of precision goes at the beginning
    thresholds = thresholds[::-1]
    for i in range(n_thresholds):
        precisions_ths[i] = sum(
            new_distances < thresholds[i])/np.size(new_distances)

    # integrate over the thresholds
    precision_auc = np.trapz(precisions_ths)
    robustness = robustness/l
    # per frame averaged intersection over union (OTB metric)
    iou = np.mean(new_ious) * 100
    return l, precision, precision_auc, iou, robustness


def _init_video(env, evaluation, video):
    video_folder = os.path.join(env.root_dataset, evaluation.dataset, video)
    video_folder_img = video_folder + "/img"
    frame_name_list = [f for f in os.listdir(
        video_folder_img) if f.endswith(".jpg")]
    frame_name_list = [os.path.join(
        env.root_dataset, evaluation.dataset, video, "img/") + s for s in frame_name_list]
    frame_name_list.sort()
    with Image.open(frame_name_list[0]) as img:
        frame_sz = np.asarray(img.size)  # im.size ⇒ (width, height)
        frame_sz[1], frame_sz[0] = frame_sz[0], frame_sz[1]

    # read the initialization from ground truth
    gt_file = os.path.join(video_folder, 'groundtruth_rect.txt')
    gt = np.genfromtxt(gt_file, delimiter=',')
    n_frames = len(frame_name_list)
    assert n_frames == len(
        gt), 'Number of frames and number of GT lines should be equal.'

    return gt, frame_name_list, frame_sz, n_frames


def _compute_distance(boxA, boxB):
    a = np.array((boxA[0]+boxA[2]/2, boxA[1]+boxA[3]/2))
    b = np.array((boxB[0]+boxB[2]/2, boxB[1]+boxB[3]/2))
    dist = np.linalg.norm(a - b)

    assert dist >= 0
    assert dist != float('Inf')

    return dist


def _compute_iou(boxA, boxB):
    # determine the (x, y)-coordinates of the intersection rectangle
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
    yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])

    if xA < xB and yA < yB:
        # compute the area of intersection rectangle
        interArea = (xB - xA) * (yB - yA)
        # compute the area of both the prediction and ground-truth
        # rectangles
        boxAArea = boxA[2] * boxA[3]
        boxBArea = boxB[2] * boxB[3]
        # compute the intersection over union by taking the intersection
        # area and dividing it by the sum of prediction + ground-truth
        # areas - the intersection area
        iou = interArea / float(boxAArea + boxBArea - interArea)
    else:
        iou = 0

    assert iou >= 0
    assert iou <= 1.01

    return iou


def convert_frames_to_video(pathIn, pathOut, fps):
    frame_array = []
    files = [f for f in os.listdir(pathIn) if isfile(join(pathIn, f))]

    # #for sorting the file names properly
    files.sort(key=lambda x: int(os.path.splitext(x)[0]))

    for i in range(len(files)):
        filename = pathIn + files[i]
        # reading each files
        img = cv2.imread(filename)
        height, width, layers = img.shape
        size = (width, height)
        # inserting the frames into an image array
        frame_array.append(img)

    out = cv2.VideoWriter(pathOut, cv2.VideoWriter_fourcc(*'DIVX'), fps, size)

    for i in range(len(frame_array)):
        # writing to a image array
        out.write(frame_array[i])
    out.release()


if __name__ == '__main__':
    evaluate()
    pathIn = './result/'
    pathOut = 'video.avi'
    fps = 25.0
    convert_frames_to_video(pathIn, pathOut, fps)
