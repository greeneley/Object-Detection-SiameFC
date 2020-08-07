import numpy as np
import matplotlib.patches as patches
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
i = 0
from pathlib import Path


def show_frame(frame, bbox, bboxA, fig_n):
    global i 
    fig = plt.figure(fig_n)
    ax = fig.add_subplot(111)

    r = patches.Rectangle((bbox[0],bbox[1]), bbox[2], bbox[3], linewidth=2, edgecolor='r', fill=False)
    #r1 = patches.Rectangle((bboxA[0] , bboxA[1]), bboxA[2], bboxA[3], color='k', alpha=0.3) 
    ax.imshow(np.uint8(frame))
    ax.add_patch(r)
    #ax.add_patch(r1)
    plt.savefig('result/'+str(i)+'.png')
    i = i + 1
    # files.download('foo.png')
    plt.ion()
    plt.show()
    plt.pause(0.001)
    plt.clf()


def show_crops(crops, fig_n):
    fig = plt.figure(fig_n)
    ax1 = fig.add_subplot(131)
    ax2 = fig.add_subplot(132)
    ax3 = fig.add_subplot(133)
    ax1.imshow(np.uint8(crops[0,:,:,:]))
    ax2.imshow(np.uint8(crops[1,:,:,:]))
    ax3.imshow(np.uint8(crops[2,:,:,:]))
    plt.ion()
    plt.show()
    plt.pause(0.001)


def show_scores(scores, fig_n):
    fig = plt.figure(fig_n)
    ax1 = fig.add_subplot(131)
    ax2 = fig.add_subplot(132)
    ax3 = fig.add_subplot(133)
    ax1.imshow(scores[0,:,:], interpolation='none', cmap='hot')
    ax2.imshow(scores[1,:,:], interpolation='none', cmap='hot')
    ax3.imshow(scores[2,:,:], interpolation='none', cmap='hot')
    plt.ion()
    plt.show()
    plt.pause(0.001)