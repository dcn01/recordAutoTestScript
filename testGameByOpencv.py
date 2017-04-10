#!/usr/bin/env python
# encoding: utf-8

import cv2
import numpy as np
import signal
import sys
import os
import time
import subprocess
import glob
import math
from os.path import getmtime
import traceback
from libs.AdbCommand import screencap
from libs.GetDeviceInfo import getDeviceInfo
from PIL import Image

currPath = os.getcwd()
queryImageRoot = os.path.join(currPath, 'imageFile/queryImage')
matchImageRoot = os.path.join(currPath, 'imageFile/matchImage')
sceneImageRoot = os.path.join(currPath, 'imageFile/sceneImage')
#thumbnail size = 1.5
#portrait_thumbnailSize = (720.0, 1280.0)
#landscape_thumbnailSize = (1280.0, 720.0)
#thumbnail size = 1.2
portrait_thumbnailSize = (900.0, 1600.0)
landscape_thumbnailSize = (1600.0, 900.0)
MIN_MATCH_COUNT = 4
finishFlag = False
#deviceName = '5LM7N16224000261'
#deviceName = 'KWG5T17105003967'  #hw P9
#deviceName = '63a9bca7'  #vivo
#deviceName = 'LGH8689e43a709'  #LG
deviceName = '635f9505'    #MI 5


def signal_handler(signal, frame):
    global finishFlag
    finishFlag = True
    print 'You pressed Ctrl+C!'

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


    kp1, desc1 = detector.detectAndCompute(img1, None)
    kp2, desc2 = detector.detectAndCompute(img2, None)
    raw_matches = matcher.knnMatch(desc1, trainDescriptors=desc2, k=2) #2特征之匹配
    p1, p2, kp_pairs = filter_matches(kp1, kp2, raw_matches)
    print '###p1 len is %d, p2 len is %d, kp_pairs len is %d' % (len(p1), len(p2), len(kp_pairs))

    if len(p1) >= MIN_MATCH_COUNT:
        H, status = cv2.findHomography(p1, p2, cv2.RANSAC, 5.0)  #获取转换矩阵
        print '****%d / %d inliers/matched' % (np.sum(status), len(status))
        if np.sum(status) < len(status)/2:
            return None, None
    else:
        H, status = None, None
        print '****%d matches found, not enough for homography estimation' % len(p1)
        return None, None

    h1, w1 = img1.shape[:2]
    h2, w2 = img2.shape[:2]
    obj_corners = np.float32([[0,0], [w1, 0], [w1, h1], [0, h1]])
    obj_corners = obj_corners.reshape(1, -1, 2)
    scene_corners = cv2.perspectiveTransform(obj_corners, H)  #坐标映射
    scene_corners = scene_corners.reshape(-1, 2)
    print int(round(scene_corners[3][0])), int(round(scene_corners[3][1])), int(round(scene_corners[1][0])), int(round(scene_corners[1][1]))
    rectangle_width = int(round(scene_corners[1][0])) - int(round(scene_corners[3][0]))
    rectangle_height = int(round(scene_corners[1][1])) - int(round(scene_corners[3][1]))

    img3 = cv2.rectangle(img2, (int(round(scene_corners[3][0])), int(round(scene_corners[3][1]))), (int(round(scene_corners[1][0])), int(round(scene_corners[1][1]))), (0, 255, 0), 3)
    resultFilePath = os.path.join(matchImageRoot, pkName, flag+'_match.png')
    cv2.imwrite(resultFilePath, img3)   #保存在原始截图上标记query pic位置的图片
    if (abs(rectangle_width) < w1/3 and abs(rectangle_height) < h1/2) or (rectangle_width > w1*1.5 and rectangle_height > h1*1.5):
        print 'rectangle_width is %d, rectangle_height is %d' % (rectangle_width, rectangle_height)
        return None, None
    mid_cordinate_x = int(round((scene_corners[3][0]+scene_corners[1][0])/2))   #计算中心坐标
    mid_cordinate_y = int(round((scene_corners[3][1]+scene_corners[1][1])/2))
    #通过特征提取的图片被缩放了，所以计算真正比例的坐标需要在将计算得到的中心坐标在放大reduceRatio
    real_x = math.floor(mid_cordinate_x * x_reduceRatio)
    real_y = math.floor(mid_cordinate_y * y_reduceRatio)
    #print 'real x: %d, real y: %d' % (real_x, real_y)
    return real_x, real_y

def thumbnail_pic(path, thumbnailSize):
    savePath = None
    try:
        im = Image.open(path)
        x, y = im.size
        #thumbnailSize = x/reduceRatio, y/reduceRatio
        im.thumbnail(thumbnailSize)
        savePath = path.replace('.png', '-thumbnail.png')
        im.save(savePath)
    except:
        print 'thumbnail_pic catch exception: %s' % str(traceback.format_exec())
    return savePath

def get_resolution():
    deviceInfo = getDeviceInfo(deviceName)
    resolutioin = deviceInfo['deviceResolution']
    splitInfo = resolutioin.split('x')
    max_width = int(splitInfo[0].split()[0])
    max_height = int(splitInfo[1].split()[0])
    return (max_width, max_height)

#小米5S检测横竖屏的时候，返回两行
#SurfaceOrientation: 0, 第一行结果一直是0
#SurfaceOrientation: 0/1, 第二行，横屏为1，竖屏为0
def check_portrait_landscape():
    checkCmd = "adb -s %s shell dumpsys input | grep 'SurfaceOrientation'  | awk '{ print $2 }'" % deviceName
    result = os.popen(checkCmd , 'r')
    content = result.readlines()
    result.close()

    screenType = 'portrait'  #默认竖屏
    print 'check portrait result is: %s' % repr(content)
    if len(content) > 0:
        orientationValue = content[len(content)-1].replace('\r\n', '')
        screenTypeValue = int(orientationValue)
        if screenTypeValue == 0 or screenTypeValue == 2:
            screenType = 'portrait'   #竖屏
        elif screenTypeValue == 1 or screenTypeValue == 3:
            screenType = 'landscape'  #横屏
        else:
            print 'dumpsys input has problem.......'
    return screenType

#360用户登录
#用户名：adb shell input text 568042716@qq.com
#回车： adb shell keyevent 66
#密码： adb shell input text 123658

if __name__ == '__main__':
    x_reduceRatio = 1   #截图横坐标缩放倍数
    y_reduceRatio = 1   #截图纵坐标缩放倍数
    queryPkDic = {}
    queryPkList = []
    for packagePath in glob.glob(os.path.join(queryImageRoot, '*/')):
        packagePath = packagePath[0:-1]
        queryPkList.append(packagePath)
    for packagePath in queryPkList:
        packageName = packagePath[packagePath.rfind('/')+1:]
        queryPkDic[packageName] = []
        for queryPic in sorted(glob.glob(os.path.join(packagePath, '*-thumbnail.png')), key=getmtime):
            queryPkDic[packageName].append(queryPic)

    clearLogCmd = 'adb shell logcat -c'
    os.system(clearLogCmd)
    #readLogcatCmd = 'adb -s %s logcat -v time' % deviceName
    readLogcatCmd = 'adb logcat -v time'
    proc = subprocess.Popen(readLogcatCmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pkName = 'noName'
    resolution = get_resolution()

    for line in proc.stdout:
        if 'ActivityManager' in line and 'Displayed' in line:
            line = line.replace('\r\n', '')
            splitLine = line.split(': ')
            pkItem = splitLine[1]
            pkSplit = pkItem.split()
            startInfo = pkSplit[1]
            pkName = startInfo[0:startInfo.find('/')]
            print pkName
            break
    proc.kill()
    proc.wait()
    print 'kill adb shell logcat thread: %d, pkName is %s' % (proc.pid, pkName)


    queryPkImageRoot = os.path.join(queryImageRoot, pkName)
    matchPkImageRoot = os.path.join(matchImageRoot, pkName)
    scenePkImageRoot = os.path.join(sceneImageRoot, pkName)
    if os.path.isdir(queryPkImageRoot) is False:
        os.makedirs(queryPkImageRoot)
    if os.path.isdir(matchPkImageRoot) is False:
        os.makedirs(matchPkImageRoot)
    else:
        os.system('rm -rf %s/*.png' % matchPkImageRoot)
    if os.path.isdir(scenePkImageRoot) is False:
        os.makedirs(scenePkImageRoot)
    else:
        os.system('rm -rf %s/*.png' % scenePkImageRoot)

    startTime = time.time()
    if queryPkDic.has_key(pkName):
        signal.signal(signal.SIGINT, signal_handler)
        picNo = 0
        time.sleep(8)

        screenType = check_portrait_landscape()
        if cmp(screenType, 'landscape') == 0:
            thumbnailSize = landscape_thumbnailSize
        else:
            thumbnailSize = portrait_thumbnailSize
        print 'thumbnailSize is %s' % str(thumbnailSize)
        if cmp(screenType, 'landscape') == 0:
            x_reduceRatio = round(resolution[0]/thumbnailSize[1],2)
            y_reduceRatio = round(resolution[1]/thumbnailSize[0],2)
        else:
            x_reduceRatio = round(resolution[0]/thumbnailSize[0],2)
            y_reduceRatio = round(resolution[1]/thumbnailSize[1],2)
        print 'resolution is %s, x_reduceRatio is %s, y_reduceRatio is %s' % (str(resolution), str(x_reduceRatio), str(y_reduceRatio))


        for queryImageThumbnailPath in queryPkDic[pkName]:
            print '#####now query image is %s' % queryImageThumbnailPath
            if finishFlag is True:
                break
            if 'goBack-thumbnail.png' in queryImageThumbnailPath:
                print 'click goBack'
                os.system('adb shell input keyevent 4')
                time.sleep(2)
            else:
                maxCmpCount = 20
                while maxCmpCount > 0 and finishFlag is False:
                    sceneFilePath = os.path.join(scenePkImageRoot, 'screen-%d.png' % picNo)
                    screencap(sceneFilePath, None)
                    sceneFileThumbnailPath = thumbnail_pic(sceneFilePath, thumbnailSize)
                    if sceneFileThumbnailPath is None:
                        maxCmpCount -= 1
                        continue
                    os.remove(sceneFilePath)    #删除未缩放的截图
                    (x,y) = getImgCordinate(queryImageThumbnailPath, sceneFileThumbnailPath, 'screen-%d' % picNo)
                    picNo += 1
                    if (x,y) != (None, None):
                        print 'matching %s' % queryImageThumbnailPath
                        print 'click %d, %d' % (x, y)
                        os.system('adb shell input tap %d %d' % (x, y))
                        time.sleep(2)
                        break
                    else:
                        maxCmpCount -= 1
                        time.sleep(2)
                    #os.remove(sceneFileThumbnailPath)    #删除缩放后的截图，只保留match后的缩放截图

    endTime = time.time()
    print 'spend time is %s' % str(round(endTime-startTime, 3))

