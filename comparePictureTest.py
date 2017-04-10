#!/usr/bin/env python
# encoding: utf-8

import cv2
import numpy as np
import sys
import os
import time
import math
from PIL import Image

currPath = os.getcwd()
queryImageRoot = os.path.join(currPath, 'imageFile/queryImage')
sceneImageRoot = os.path.join(currPath, 'imageFile/sceneImage')
matchImageRoot = os.path.join(currPath, 'imageFile/matchImage')
reduceRatio = 1.2   #截图缩放倍数

def filter_matches(kp1, kp2, matches, ratio = 0.75):
    mkp1, mkp2 = [], []
    for m in matches:
        if len(m) == 2 and m[0].distance < m[1].distance * ratio:
            m = m[0]
            mkp1.append( kp1[m.queryIdx] )
            mkp2.append( kp2[m.trainIdx] )
    p1 = np.float32([kp.pt for kp in mkp1])
    p2 = np.float32([kp.pt for kp in mkp2])
    kp_pairs = zip(mkp1, mkp2)
    return p1, p2, list(kp_pairs)

def getImgCordinate(filePath, sceneFilePath, flag):
    img1 = cv2.imread(filePath)
    img2 = cv2.imread(sceneFilePath)
    detector = cv2.AKAZE_create()  #特征识别算法初始化
    norm = cv2.NORM_HAMMING
    matcher = cv2.BFMatcher(norm)

    if img1 is None:
        print 'Failed to load fn1:', filePath
        sys.exit(1)

    if img2 is None:
        print 'Failed to load fn2:', sceneFilePath
        sys.exit(1)

    if detector is None:
        print 'unknown feature'
        sys.exit(1)

    print 'using akaze'

    kp1, desc1 = detector.detectAndCompute(img1, None)
    kp2, desc2 = detector.detectAndCompute(img2, None)
    print 'matching....'
    raw_matches = matcher.knnMatch(desc1, trainDescriptors=desc2, k=2) #2特征之匹配
    p1, p2, kp_pairs = filter_matches(kp1, kp2, raw_matches)
    print len(p1), len(p2), len(kp_pairs)

    h1, w1 = img1.shape[:2]
    h2, w2 = img2.shape[:2]
    print '%s, w=%d, h=%d' % (filePath, w1, h1)
    print '%s, w=%d, h=%d' % (sceneFilePath, w2, h2)

    if len(p1) >= 4:
        H, status = cv2.findHomography(p1, p2, cv2.RANSAC, 5.0)  #获取转换矩阵
        print '%d / %d inliers/matched' % (np.sum(status), len(status))
    else:
        H, status = None, None
        print '%d matches found, not enough for homography estimation' % len(p1)
        return None, None

    obj_corners = np.float32([[0,0], [w1, 0], [w1, h1], [0, h1]])
    obj_corners = obj_corners.reshape(1, -1, 2)
    scene_corners = cv2.perspectiveTransform(obj_corners, H)  #坐标映射
    scene_corners = scene_corners.reshape(-1, 2)
    print int(round(scene_corners[3][0])), int(round(scene_corners[3][1])), int(round(scene_corners[1][0])), int(round(scene_corners[1][1]))
    rectangle_width = int(round(scene_corners[1][0])) - int(round(scene_corners[3][0]))
    rectangle_height = int(round(scene_corners[1][1])) - int(round(scene_corners[3][1]))
    img3 = cv2.rectangle(img2, (int(round(scene_corners[3][0])), int(round(scene_corners[3][1]))), (int(round(scene_corners[1][0])), int(round(scene_corners[1][1]))), (0, 255, 0), 3)
    resultFilePath = os.path.join(matchImageRoot, pkName, flag+'_match.png')
    cv2.imwrite(resultFilePath, img3)
    if (rectangle_width < w1/2 and rectangle_height < h1/2) or (rectangle_width > w1*1.5 and rectangle_height > h1*1.5):
        print 'rectangle_width is %d, rectangle_height is %d' % (rectangle_width, rectangle_height)
        return None, None
    mid_cordinate_x = int(round((scene_corners[3][0]+scene_corners[1][0])/2))   #计算中心坐标
    mid_cordinate_y = int(round((scene_corners[3][1]+scene_corners[1][1])/2))
    #通过特征提取的图片被缩放了，所以计算真正比例的坐标需要在将计算得到的中心坐标在放大reduceRatio
    return math.floor(mid_cordinate_x*reduceRatio), math.floor(mid_cordinate_y*reduceRatio)

def thumbnail_pic(path):
    im = Image.open(path)
    x, y = im.size
    print '%s, w=%d,h=%d' % (path, x, y)
    thumbnailSize_x = int(math.ceil(x/reduceRatio))
    thumbnailSize_y = int(math.ceil(y/reduceRatio))
    thumbnailSize = (thumbnailSize_x, thumbnailSize_y)
    im.thumbnail(thumbnailSize)
    savePath = path.replace('.png', '-thumbnail.png')
    #im.resize(thumbnailSize, Image.ANTIALIAS).save(savePath)
    im.save(savePath)
    return savePath


if __name__ == '__main__':
    pkName = 'com.babeltime.fknsg2.qihoo'

    queryPkImageRoot = os.path.join(queryImageRoot, pkName)
    matchPkImageRoot = os.path.join(matchImageRoot, pkName)
    scenePkImageRoot = os.path.join(sceneImageRoot, pkName)
    if os.path.isdir(queryPkImageRoot) is False:
        os.makedirs(queryPkImageRoot)
    if os.path.isdir(matchPkImageRoot) is False:
        os.makedirs(matchPkImageRoot)
    if os.path.isdir(scenePkImageRoot) is False:
        os.makedirs(scenePkImageRoot)
    startTime = time.time()
    queryImagePath = os.path.join(queryPkImageRoot, 'skipAmination-thumbnail.png')
    sceneFilePath = os.path.join(scenePkImageRoot, 'screen-17-thumbnail.png')
    #queryImageThumbnailPath = thumbnail_pic(queryImagePath)
    #sceneFileThumbnailPath = thumbnail_pic(sceneFilePath)
    queryImageThumbnailPath = queryImagePath
    sceneFileThumbnailPath = sceneFilePath

    print getImgCordinate(queryImageThumbnailPath, sceneFileThumbnailPath, 'start')
    endTime = time.time()
    print 'spend time is %s' % str(round(endTime-startTime, 3))


