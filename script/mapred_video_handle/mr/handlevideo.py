#!/usr/bin/env python
# -*- encoding:utf-8 -*-

'''
Created on Oct 25, 2012

@author: wye

Copyright @ 2011 - 2012  Cloudiya Tech . Inc 
'''


"""
对视频进行预处理
"""

import os
import sys
import time
import json
import ujson
import Image
import pickle
import random
import logging
import operator
import optparse
import baseclass
import subprocess
import xml.etree.ElementTree as ET

###############################################

# --/
#     常量
# --/

FFPROBE="/usr/local/bin/ffprobe"

###############################################

# --/
#     初始化日志对象
# --/

logger = baseclass.getlog("handlevideo")

###############################################

# --/
#
#    获取命令行参数
#    '-m' : 视频文件信息,xml文件.
#    '-d' : hadoop安装目录,在所有相关主机hadoop安装目录需一致.
#    '-n' : mapreducer集群namenode+port
#    '-z' : hdfs集群namenode+port
#    '-t' : tasktracker节点数
#    '-b' : 指定块尺寸
#    '-v' : hadoop版本
#    '-l' : 指定日志级别,info或debug
#    
#    例: python handlevideo.py  -m 9527kok.xml  -d /opt/cloudiyaDataCluster/hadoop -z 192.168.0.112:50081 -n 192.168.0.112:50081 -t 4 -b 16 -v 1.0.3 -l debug
#
# --/


def get_file_from_hdfs(Hadoopcommand,URL,localpath,Maxtime=5):
    '''默认从远程获取5次，如果5次都不能成功那么获取水印文件失败，退出'''
    HadoopBin = Hadoopcommand
    hdfs_url = URL
    local_path = localpath
    This_time = Maxtime
    if This_time == 0:
        return False
    else:
        cmd = "%s fs -copyToLocal %s %s"%(HadoopBin,hdfs_url,local_path)
        retcode = subprocess.call(cmd,shell=True,stdout=open('/dev/null'),stderr=subprocess.STDOUT)
        if retcode != 0:
            get_file_from_hdfs(HadoopBin,hdfs_url,local_path,This_time-1)
        else:
            return True

def calRealWmarkSize(vwidth,vheight,wwidth,wheight):
    RealWmarkFileHeight = int(vheight/8)
    RealWmarkFileWidth = int(RealWmarkFileHeight*wwidth/wheight)
    return RealWmarkFileWidth,RealWmarkFileHeight
        
def calWmarkCoordinates(vwidth,vheight,wwidth,wheight,wmarkposition):
    '''计算水印坐标值并返回'''
    if wmarkposition == "0":
        LeftPixels = vwidth*0.1
        UpPixels = vheight*0.1
    if wmarkposition == "1":
        RemainLength = vwidth - wwidth
        if RemainLength > vwidth*0.1:
            LeftPixels = RemainLength - vwidth*0.1
        elif 0 < RemainLength <= vwidth*0.1:
            LeftPixels = RemainLength*0.9
        else:
            LeftPixels = RemainLength
        UpPixels = vheight*0.1
    if wmarkposition == "3":
        LeftPixels = vwidth*0.1
        RemainLength = vheight - wheight
        if RemainLength > vheight*0.1:
            UpPixels = RemainLength - vheight*0.1
        elif 0 < RemainLength <= vheight*0.1:
            UpPixels = RemainLength*0.9
        else:
            UpPixels = RemainLength
    if wmarkposition == "2":
        #计算距离左边像素值
        RemainLengthw = vwidth - wwidth
        if RemainLengthw > vwidth*0.1:
            LeftPixels = RemainLengthw - vwidth*0.1
        elif 0 < RemainLengthw <= vwidth*0.1:
            LeftPixels = RemainLengthw*0.9
        else:
            LeftPixels = RemainLengthw
        #计算距离上边像素值
        RemainLengthh = vheight - wheight
        if RemainLengthh > vheight*0.1:
            UpPixels = RemainLengthh - vheight*0.1
        elif 0 < RemainLengthh <= vheight*0.1:
            UpPixels = RemainLengthh*0.9
        else:
            UpPixels = RemainLengthh 
        
    return LeftPixels,UpPixels
      
        
try:
    
    cmdopt = optparse.OptionParser(description="video handle related parameter",
                                   prog="handlevideo.py" ,
                                   version="1.0",
                                   usage="%prog --vmatadata  video metadata information file     \
                                                --hadinsdir    hadoop install direction          \
                                                --nnport  hadoop namenode ipaddress+port         \
                                                --snnport store hadoop namenode ipaddress+port   \
                                                --tasknums  tasktracker node numbers             \
                                                --blocksize hadoop block size                    \
                                                --hadversion  hadoop version                     \
                                                --loglevel setup log level                       \
                                                ")
    
    cmdopt.add_option('-m','--vmatadata', help="video metadata information file")
    cmdopt.add_option('-d','--hadinsdir', help="hadoop install direction")
    cmdopt.add_option('-n','--nnport',    help="hadoop namenode ipaddress+port")
    cmdopt.add_option('-z','--snnport',   help="store hadoop namenode ipaddress+port")
    cmdopt.add_option('-t','--tasknums',  help="tasktracker node numbers")
    cmdopt.add_option('-b','--blocksize', help="hadoop block size")
    cmdopt.add_option('-v','--hadversion',help="hadoop version")
    cmdopt.add_option('-l','--loglevel',  help="setup log level")
    
    options,arguments = cmdopt.parse_args()
    
    VideoMetaFile = options.vmatadata.strip()          
    HadoopInsDir = options.hadinsdir.strip()
    HadoopNNAddr = options.nnport.strip()              
    HadoopSNNAddr = options.snnport.strip()           
    TaskTrackerNums = int(options.tasknums.strip())    
    BlockSize = int(options.blocksize.strip())         
    HadoopVersion = options.hadversion.strip()         
    LogLevel = options.loglevel.strip()  
    
    myselfdir = os.path.split(os.path.realpath(__file__))[0]
    HadoopBinDir = HadoopInsDir + "/bin/hadoop"
    HadoopStreamJarPath = HadoopInsDir + "/contrib/streaming/hadoop-streaming-%s.jar"%(HadoopVersion)
    
    logger.info("handle video parameter info :  \n \
                  VideoMetaFile: %s             \n \
                  HadoopInsDir : %s             \n \
                  HadoopNNAddr : %s             \n \
                  HadoopSNNAddr : %s            \n \
                  TaskTrackerNums : %s          \n \
                  BlockSize : %s                \n \
                  HadoopVersion : %s            \n \
                  LogLevel : %s                 \n \
                  "%(VideoMetaFile,HadoopInsDir,HadoopNNAddr,HadoopSNNAddr,TaskTrackerNums,BlockSize,HadoopVersion,LogLevel))          

except Exception,e:
    logger.error("Command line parameter exception : %s,program quit"%e)
    sys.exit()
    
###################################################


# --/
#     解析视频信息xml文件,获取视频相关信息. 
# --/

try:
    
    # --/
    #     解析视频信息xml文件,获取视频相关信息.
    #     VideoFileNameAlias ： 视频别名,即vid
    #     VideoFilePath      ： 视频文件本地硬盘路径
    #     OriginVideoFormat  ： 视频文件扩展名
    #     IsWaterMark        ： 打水印标志
    #     WaterMarkPath      ： 水印图片在本地硬盘路径
    #     LeftPixels         ： 水印距离播放器左边框像素值
    #     UpPixels           ： 水印距离播放器上边框像素值
    #     wmarkposition      ： 水印位置
    #                           0 :  左上
    #                           1 :  右上
    #                           2 :  左下
    #                           3 :  右下  
    # --/
    
    
    if not os.path.isfile(VideoMetaFile):
        logger.error("Don't find video metadata file in local disk : %s"%VideoMetaFile)
        sys.exit()
        
    xmltree = ET.parse(VideoMetaFile)
    xmlroot = xmltree.getroot()
    
    VideoFileNameAlias = xmlroot.find("name").text
    VideoFilePath = xmlroot.find("path").text
    OriginVideoFormat = VideoFilePath.split(".")[-1].lower()
    
    IsWaterMark = xmlroot.find("wmark").text
    if IsWaterMark == "True":
        
        WaterMarkPath = xmlroot.find("wmarkpath").text
        wmarkposition = str(xmlroot.find("wmarkposition").text)
        LeftPixels = xmlroot.find("lpixels").text
        UpPixels = xmlroot.find("upixels").text
        
        IsWaterMark = True
    else:
        IsWaterMark = False
        WaterMarkPath,LeftPixels,UpPixels = None,None,None
        
    IsOverWrite = xmlroot.find("overwrite").text
    
    MysqlObj = baseclass.interWithMysql(logger,VideoFileNameAlias)

    if IsOverWrite == "True":
        IsOverWrite = True
        
        #预览图状态,1表示用默认图片,2表示用户有上传自定义的预览图
        pstat = MysqlObj.getPicStatus()
        
    else:
        IsOverWrite = False

    logger.info("video info :             \n  \
                    VideoFileNameAlias : %s  \n  \
                    VideoFilePath : %s       \n  \
                    OriginVideoFormat ： %s  \n  \
                    IsWaterMark : %s         \n  \
                    WaterMarkPath : %s       \n  \
                    IsOverWrite : %s         \n  \
           "%(VideoFileNameAlias,VideoFilePath,OriginVideoFormat,IsWaterMark,WaterMarkPath,IsOverWrite))
        
except Exception,e:
    logger.error("Parse video info xml file exception : %s,program quit"%e)
    sys.exit()   


###########################################################################
# --/
#       判断该文件是否存在于本地，如果本地不存在，那么尝试从hdfs中获取.2种方式获取失败则退出
# --/

vid = VideoFileNameAlias
uid = vid[0:4]
VideoFileName = VideoFilePath.split("/")[-1]
VideoFilePathHdfs = "hdfs://%s/static/%s/%s" % (HadoopSNNAddr,uid,vid)
VideoFileInHdfs =  "hdfs://%s/static/%s/%s" % (HadoopSNNAddr,uid,VideoFileName)
VideoFileInHdfs_New = "/static/%s/%s/play.mp4" % (uid,vid)

logger.info("ready to get file....")

# --/
#     重新初始化日志对象,执行命令对象,本地临时文件存储环境
# --/

#重新初始化日志对象
logger = baseclass.getlog(vid,loglevel=LogLevel)
logger.info("ready to go....")

#初始化mysql对象
MysqlObj = baseclass.interWithMysql(logger,vid)

#初始化执行命令对象
RunCmdObj = baseclass.runCmd(logger,vid,IsWaterMark,IsOverWrite)
logger.info("runcomdobj init...")

#初始化Hadoop对象
#HdfsObj = baseclass.hdfs(logger,vid,HadoopBinDir)

#初始化webhadoop,mapper对象
MapHost = HadoopNNAddr.split(":")[0]
MapWebHdfs = baseclass.WebHadoopOld(MapHost,"50071","cloudiyadatauser",logger)

#初始化webhadoop，storage对象
StoHost = "10.2.0.8,10.2.0.10"
StoWebHdfs = baseclass.WebHadoop(StoHost,14000,"cloudiyadatauser",logger)

logger.info("yes ,the obj init finished...")


if os.path.isfile(VideoFilePath) == False:
    if StoWebHdfs.get_file(VideoFilePath,VideoFileInHdfs_New):
        logger.info("Successfully obtain the file from HDFS!")
    else:
        MysqlObj.writeStatus("fail",IsWaterMark,IsOverWrite,info="Cannot obtain the file from HDFS!")
        sys.exit()
else:
    logger.info("Successfully obtain the file locally")


#初始化本地临时文件存储环境
VideoTmpDir = "/tmp/%s" % (vid)
VideoTmpInputDir = VideoTmpDir + "/inputfiles"
VideoTmpAvfilesDir = VideoTmpDir + "/avfiles" 
if os.path.exists(VideoTmpDir):
    if os.path.isdir(VideoTmpInputDir) == False:
        logger.info("WARNING: inputDir %s doesn't exist, make the inputDir now!" % (vid))
        try:
            os.mkdir(VideoTmpInputDir)
        except Exception,e :
            logger.error("Can't create %s directory! ERROR :"%(VideoTmpInputDir,e))
            MysqlObj.writeStatus("fail",IsWaterMark,IsOverWrite,info="can't create tmp directory!")
            sys.exit()              
    
    if os.path.isdir(VideoTmpAvfilesDir) == False:
        logger.info("WARNING: avfilesDir %s doesn't exist, make this avfilesDir now!" % (VideoTmpAvfilesDir))
        try:
            os.mkdir(VideoTmpAvfilesDir)
        except Exception,e :
            logger.error("Can't create %s directory! ERROR :"%(VideoTmpAvfilesDir,e))
            MysqlObj.writeStatus("fail",IsWaterMark,IsOverWrite,info="can't create tmp avfiles directory!")
            sys.exit() 
                
else:
    RunCmdObj.run(["mkdir /tmp/%s && mkdir /tmp/%s/inputfiles && mkdir /tmp/%s/avfiles"%(vid,vid,vid)])

##########################################################

# --/
#     局部变量初始化
# --/

BitRate,VideoSize,VideoDuration = None,None,None

VideoBitRate,VideoFrameWidth,VideoFrameHeight,VideoCode = None,None,None,None

AudioBitRate,AudioCode,AudioSampleRate,AudioChannels = None,None,None,None

# --/
#     获取视频元数据信息
# --/

try:
    
    # --/
    #     以下信息由调用系统命令'ffprobe -show_format' , 'ffprobe -show_streams'获得.
    #     BitRate           :  总码率
    #     VideoBitRate      :  视频流码率
    #     AudioBitRate      :  音频流码率
    #     VideoFrameWidth   :  视频帧宽度值
    #     VideoFrameHeight  :  视频帧高度值
    #     VideoDuration     :  视频时长
    #     VideoSize         :  视频大小
    #     VideoCode         :  视频编码方式
    #     AudioCode         :  音频编码方式
    #     AudioSampleRate   :  音频采样率
    #     AudioChannels     :  音频声道,单声道或双声道.
    # --/
    
    
    RunCmdObj.run(["%s -show_format %s"%(FFPROBE,VideoFilePath)])
    VFormatList = baseclass.getVideoMetaDList(RunCmdObj.stdout,"FORMAT")
    
    VFormatDict = VFormatList[0]
    
    VideoSize = int(VFormatDict["size"])
    BitRate = VFormatDict["bit_rate"]
    VideoDuration = float(VFormatDict["duration"])
    
    StreamNum = int(VFormatDict["nb_streams"])
    
    RunCmdObj.run(["%s -show_streams %s"%(FFPROBE,VideoFilePath)])
    VStreamsList = baseclass.getVideoMetaDList(RunCmdObj.stdout,"STREAM")
    
    
    # --/
    #     依据视频文件包含的流个数和类型进行处理
    # --/
    
    VStream = 0
    AStream = 0
    
    for i in range(StreamNum):
        if VStreamsList[i]["codec_type"] == "video":
            VStream = VStream + 1
            if VStream == 1:
                VStreamsVDict = VStreamsList[i]
        if VStreamsList[i]["codec_type"] == "audio":
            AStream = AStream + 1
            if AStream == 1:
                VStreamsADict = VStreamsList[i]
    
        
    if VStream >= 1 and AStream >= 1:
        
        # --/
        #     视频流与音频流都存在
        # --/
                
        VFlag = "all"
        
        VideoBitRate = VStreamsVDict["bit_rate"]
        VideoCode = VStreamsVDict["codec_name"]
        VideoFrameWidth = int(VStreamsVDict["width"])
        VideoFrameHeight = int(VStreamsVDict["height"])
        
        AudioBitRate = VStreamsADict["bit_rate"]
        AudioCode = VStreamsADict["codec_name"]
        AudioSampleRate = VStreamsADict["sample_rate"]
        AudioChannels = int(VStreamsADict["channels"])
        
    elif VStream >= 1 and AStream == 0:
        
        # --/
        #     只存在视频流,无音频流.
        # --/
        
        VFlag = "video"

        AudioBitRate = 2
        AudioCode = "aac"
        AudioSampleRate= 48000
        AudioChannels = 2

        VideoBitRate = VStreamsVDict["bit_rate"]
        VideoCode = VStreamsVDict["codec_name"]
        VideoFrameWidth = int(VStreamsVDict["width"])
        VideoFrameHeight = int(VStreamsVDict["height"])
        
    else:
        
        # --/
        #     只存在音频,无视频流等,程序退出.
        # --/
        
        logger.error("Does not meet the video processing conditions,nb_streams is %s"%StreamNum)
        MysqlObj.writeStatus("fail",IsWaterMark,IsOverWrite,info="Does not meet the video processing conditions")
        sys.exit()
    
    # --/
    #      写视频基本信息到mysql数据库
    # --/
    MysqlObj.writeVinfo(BitRate,VideoBitRate,AudioBitRate,VideoFrameWidth,VideoFrameHeight,VideoDuration,VideoSize,OriginVideoFormat)
    
    logger.debug("video metadata info :   \n  \
                  VFlag   : %s            \n  \
                  BitRate : %s            \n  \
                  VideoSize : %s          \n  \
                  VideoDuration : %s      \n  \
                  VideoBitRate : %s       \n  \
                  VideoFrameWidth : %s    \n  \
                  VideoFrameHeight : %s   \n  \
                  VideoCode : %s          \n  \
                  AudioBitRate : %s       \n  \
                  AudioCode : %s          \n  \
                  AudioSampleRate : %s    \n  \
                  AudioChannels : %s      \n  \
                  "%(VFlag,BitRate,VideoSize,VideoDuration,VideoBitRate,VideoFrameWidth,VideoFrameHeight,VideoCode,AudioBitRate,AudioCode,AudioSampleRate,AudioChannels))

except Exception,e:
    logger.error("Obtain video file metadata exception : %s,program quit"%e)
    MysqlObj.writeStatus("fail",IsWaterMark,IsOverWrite,info="Obtain video file metadata exception")
    sys.exit()   

###################################################

# --/
#     分割视频,调整时间偏移.
# --/

BlockSizeList = [128,64,32,8]
BlockSizeList.append(BlockSize)

try:
    
    while True:
        # --/
        #     分割视频准备工作,依据指定块大小将计算视频文件将分成几块
        # --/
        try:
            BlockSize = BlockSizeList.pop()
            logger.info("Now BlockSize is %s"%(BlockSize))
        except IndexError:
            logger.error("Video files can not be processed!!!")
            MysqlObj.writeStatus("fail",IsWaterMark,IsOverWrite,info="Video files can not be processed!!!")
            sys.exit()
        
        PerSecondSizeByte = operator.div(VideoSize,VideoDuration)
        BlockSizeSecondNum = int(operator.div(BlockSize*1024*1024,PerSecondSizeByte))
        
        PartNums = int(operator.itruediv(VideoDuration,BlockSizeSecondNum))+1
        
        logger.debug("split video information : \n \
                      PerSecondSizeByte : %s    \n \
                      BlockSizeSecondNum : %s   \n \
                      VideoSegNums : %s         \n \
                     "%(PerSecondSizeByte,BlockSizeSecondNum,PartNums))
        
        
        # --/
        #     调用handleoffset.sh脚本,对视频进行预处理
        # --/
           
        cmd = "cd /tmp/%s/ && /bin/sh %s/handleoffset.sh %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s"
        cmdstr = cmd%(vid,myselfdir,VideoFilePath,vid,OriginVideoFormat,PartNums,BlockSizeSecondNum,VideoDuration,
                      VFlag,BitRate,VideoBitRate,VideoCode,AudioBitRate,AudioCode,AudioSampleRate,AudioChannels,myselfdir)
        RunCmdObj.run([cmdstr])
        
        ShellReturnDict = json.loads(RunCmdObj.stdout[0].strip())
       
        logger.info("shell return dict is : %s"%(ujson.encode(ShellReturnDict)))
 
        if ShellReturnDict["IsHaveStream"] == "YES":
            break
        else:
            logger.debug("Now ,ready to delete files in /tmp/%s/avfiles/*"%(vid))
            RunCmdObj.run(["rm -f /tmp/%s/avfiles/*"%(vid)])
        
    NewVideoFormat = ShellReturnDict["suffix"]
    VideoBitRate = int(ShellReturnDict["vb"])
    AudioBitRate = int(ShellReturnDict["ab"])
    PartNums = int(ShellReturnDict["RealPartNums"])

    logger.debug("Shell return data :   \n \
                  New video format : %s \n \
                  Video bitrate : %s    \n \
                  Audio bitrate : %s    \n \
                  Real PartNums : %s    \n \
                 "%(NewVideoFormat,VideoBitRate,AudioBitRate,PartNums))

    
    # --/
    #     为mapreducer处理准备文件
    # --/
    
    
    def getPartsAssignList(PartNums,TaskTrackerNums):
        list = []
        for i in range(TaskTrackerNums):
            list.append(0)
            
        def listsum(list):
            sum = 0
            for i in list:
                sum = i + sum
            return sum
        
        loop = False
        while not loop:
            for i in range(TaskTrackerNums):
                list[i] = list[i]+1
                if listsum(list) == PartNums:
                    loop = True
                    break
        return list
    
    i = PartNums
    p = 0
    for n in getPartsAssignList(PartNums,TaskTrackerNums):
        p = p+1
        while n > 0:
            #print "part%sv.mp4 , %s "%(i,p)
            cmdstr = "echo \"part%sv.%s\" >> /tmp/%s/inputfiles/video_%s"%(i,NewVideoFormat,vid,p)
            RunCmdObj.run([cmdstr])
            i=i-1
            n=n-1
    
except Exception,e:
    logger.error("Split video exception : %s , program quit"%e)
    MysqlObj.writeStatus("fail",IsWaterMark,IsOverWrite,info="Split video exception")
    sys.exit()

#############################################################

# --/
#     处理视频原始文件和水印文件,包括:
#     上传原始文件到存储hdfs集群
#     如需打水印将水印文件移到本地临时文件夹
# --/

###################################################

# 
# 判断文件是否已经被处理过，如果已经被处理过，那么先备份原目录为 $DIR-TMP 
# 并删除mapreduce处理的临时目录
#

File_dir_Path = "/static/%s/%s" % (uid,vid)
BakcupPathHdfs_NEW = File_dir_Path + "-TMP"
BackupPathHdfs = VideoFilePathHdfs + "-TMP"
if IsOverWrite:
    StoWebHdfs.lsdir(File_dir_Path) 
    if StoWebHdfs.status == 200 :
        StoWebHdfs.rename(File_dir_Path,BakcupPathHdfs_NEW)
        if StoWebHdfs.status == 200:
            logger.info("Successfully rename %s directory in HDFS" % vid)
        else:
            MysqlObj.writeStatus("fail",IsWaterMark,IsOverWrite,info="Failed to rename the directory in HDFS")
            sys.exit()       
        
    # next, to remove TMP directory for mapreduce processing in HDFS
    MapTmpPath = "hdfs://%s/%s" % (HadoopNNAddr,vid)
    MapTmpPath_new = "/%s" % vid
    MapWebHdfs.lsdir(MapTmpPath_new)
    
    if MapWebHdfs.status == 200:
        MapWebHdfs.remove(MapTmpPath_new)
        if MapWebHdfs.status == 200:
            logger.info("Successfully delete TMP directory for MapReduce")
        else:
            MysqlObj.writeStatus("fail",IsWaterMark,IsOverWrite,info="Failed to delete TMP directory for MapReduce")
            sys.exit()        

#
# 检查hadoop中是否有vid目录; 如果没有就新建vid目录
#

StoWebHdfs.lsdir(File_dir_Path)
if StoWebHdfs.status == 404:
    StoWebHdfs.mkdir(File_dir_Path)
    if  not StoWebHdfs.mkdir(File_dir_Path):
        MysqlObj.writeStatus("fail",IsWaterMark,IsOverWrite,info="Failed to create directory in HDFS")
        sys.exit()
    else:
        logger.info("Successfully create HDFS directory %s" % VideoFilePathHdfs)
else:
    logger.info("HDFS directory %s already exists HDFS" % vid)

#
# 保留vid目录的用户自定义preview picture，如果有的话
#
# to do:
#    this cp function in webhadoop will be supported in future.
if IsOverWrite and pstat==2:
    # preview picture is in @param File_dir_Path
    preview_pic_list = []
    files_list = StoWebHdfs.lsdir(BakcupPathHdfs_NEW)
    if len(files_list) == 0 :
        logger.info("WARNING: there is no files in dir %s hadoop cluster!" % BakcupPathHdfs_NEW)
    else:
        for x,y in enumerate(files_list):
            if y['type'] == "FILE":
                if "preview" in y['pathSuffix']:
                    previw_name = y['pathSuffix']
                    preview_pic_list.append(previw_name)
    if len(preview_pic_list) != 0:
        for prev in preview_pic_list:
            Prev_Backup_Path = BakcupPathHdfs_NEW + "/" + prev
            Prev_new_Path = File_dir_Path + "/" + prev
            if StoWebHdfs.copy_in_hdfs(Prev_Backup_Path,Prev_new_Path):
                logger.info("Successfully preserve the preview picture")
            else:
                logger.info("WARNING: unable to preserve the preview picture!")    

#
# 检查hdfs vid目录下是否存在该视频原始文件,不存在则上传.
#
#如需要加水印,将水印文件复制到待处理视频临时文件夹.
#默认的文件存在于hdfs中。需要先从hdfs中下载到本地处理
#

if IsWaterMark:
    #判断文件的后缀名
    logo_extension_list = ["png","jpg"]
    logo_extension_name = WaterMarkPath.split(".")[-1]
    WaterMarkPath_New = WaterMarkPath.split("50081")[-1]
    if logo_extension_name in logo_extension_list :
        #判断文件是否存在于本地，如果没有，则从hdfs中获取中。
        tmp_logo_path = "/tmp/%s/logo.%s" % (vid,logo_extension_name)
    else:
        MysqlObj.writeStatus("fail",IsWaterMark,IsOverWrite,info="ERROR: LOGO file format not supported")
        sys.exit()        

    if os.path.isfile(tmp_logo_path):
        logger.info("Logo file exists locally")
    else:
        StoWebHdfs.lsfile(WaterMarkPath_New)
        if StoWebHdfs.status == 200:
            if StoWebHdfs.get_file(tmp_logo_path,WaterMarkPath_New):
                logger.info("Successfully obtain watermark file from HDFS")
            else:
                MysqlObj.writeStatus("fail",IsWaterMark,IsOverWrite,info="Failed to obtain watermark file from HDFS")
                sys.exit()
        else:
            MysqlObj.writeStatus("fail",IsWaterMark,IsOverWrite,info="Failed to obtain watermark file locally")
            sys.exit()
            
    if not IsOverWrite:  
        #上传视频时打水印
        im = Image.open(tmp_logo_path)
        WmarkFileWidth = im.size[0]
        WmarkFileHeight = im.size[1]
        RealWmarkFileWidth,RealWmarkFileHeight = calRealWmarkSize(int(VideoFrameWidth),int(VideoFrameHeight),int(WmarkFileWidth),int(WmarkFileHeight))
        LeftPixels,UpPixels = calWmarkCoordinates(int(VideoFrameWidth),int(VideoFrameHeight),int(RealWmarkFileWidth),int(RealWmarkFileHeight),wmarkposition)
        if LeftPixels <= 0 or UpPixels <= 0:
            MysqlObj.writeStatus("fail",IsWaterMark,IsOverWrite,info="Watermark file size problem")
            sys.exit()    
###################################################

# -- /
#      将本地临时文件夹中数据上传到mapreducer集群,如果集群中原来的文件，那么删除后再上传
# -- /

cmd1 = "cd /tmp/%s && rm -f *.txt *.ts *part* ma.* mv.* && rm -rf mrdata"%(vid)
RunCmdObj.run([cmd1])
TmpDir_Path = "/tmp/%s" % vid
TmpHdfs_Path = "/%s" % vid
if MapWebHdfs.put_dir(TmpDir_Path,TmpHdfs_Path,overwrite="true"):
    logger.info("Great,successful put the dir %s into hadoop cluster.." % TmpDir_Path)
else:
    logger.error("Sorry,putting the dir %s into hadoop cluster failure!!!" % TmpDir_Path)

#cmd3 = "rm -rf /tmp/%s/* "%(vid)
#RunCmdObj.run([cmd3])

###################################################

# --/
#     为mapreducer准备常量数据
# --/

if IsWaterMark:
    info_dict = {'name':vid,'duration':VideoDuration,'width':VideoFrameWidth,'height':VideoFrameHeight,'vbitrate':VideoBitRate,'abitrate':AudioBitRate,'iswatermark':IsWaterMark,'leftpixels':LeftPixels,'uppixels':UpPixels,'logoextname':logo_extension_name,'isoverwrite':IsOverWrite}

    logger.info("watermark related info : \n \
                 VideoFrameWidth : %s     \n \
                 VideoFrameHeight: %s     \n \
                 LeftPixels     : %s      \n \
                 UpPixels       : %s      \n \
                 "%(VideoFrameWidth,VideoFrameHeight,LeftPixels,UpPixels))

else:
    info_dict = {'name':vid,'duration':VideoDuration,'width':VideoFrameWidth,'height':VideoFrameHeight,'vbitrate':VideoBitRate,'abitrate':AudioBitRate,'iswatermark':IsWaterMark,'isoverwrite':IsOverWrite}

hadoopinfo_dict = {"HadoopNNAddr":HadoopNNAddr,"HadoopBinDir":HadoopBinDir,"HadoopSNNAddr":HadoopSNNAddr}

info_dict['segmentnums'] = PartNums
info_dict['blockduration'] = BlockSizeSecondNum
info_dict['loglevel'] = LogLevel

RunCmdObj.run(["mkdir -p /tmp/%s/mrdata "%(vid)])

f = open('/tmp/%s/mrdata/video.info'%vid,'w')
pickle.dump(info_dict,f)
f.close()

f = open('/tmp/%s/mrdata/hadoop.info'%vid,'w')
pickle.dump(hadoopinfo_dict,f)
f.close()

cmd = "cp %s/mapper.py  %s/reducer.py  %s/baseclass.py /tmp/%s/mrdata/"%(myselfdir,myselfdir,myselfdir,vid)
RunCmdObj.run([cmd])

####################################################

# --/
#     mapreducer处理
# --/

logger.info("Pre-processing handle %s.%s file complete"%(vid,OriginVideoFormat))
logger.info("Start mapreducer handle, plase wait....")

cmd = "(time %s jar %s  -file /tmp/%s/mrdata/  -mapper mapper.py  -reducer reducer.py -input hdfs://%s/%s/inputfiles -output hdfs://%s/%s/%s -numReduceTasks 1) >> /tmp/videohandle.log 2>&1"
cmdstr = cmd%(HadoopBinDir,HadoopStreamJarPath,vid,HadoopNNAddr,vid,HadoopNNAddr,vid,vid)
RunCmdObj.run([cmdstr],QuitFlag=False)


####################################################

# --/
#     删除临时数据
# --/


#判断处理后的状态值，如果处理失败，并且不是第一次打水印，回滚到上一次的视频文件
status = MysqlObj.getStatus()
if int(status) == 12 or int(status) == 34 :
    logger.info("ERROR: MapReduce processing for %s FAILED"%(vid))
    if IsOverWrite:
        logger.info("Trying to roll back to the original files...")
        StoWebHdfs.remove(File_dir_Path)
        StoWebHdfs.rename(BakcupPathHdfs_NEW,File_dir_Path)
        if StoWebHdfs.status == 200:
            MysqlObj.writeStatus("success",IsWaterMark,IsOverWrite,info="Cannot watermark, but files have been rolled back")
        else:
            MysqlObj.writeStatus("fail",IsWaterMark,IsOverWrite,info="Cannot watermark, and FAILED to roll back")
            sys.exit()      
    else:
        sys.exit()    
else:
    logger.info("Successfully process the file ......")
    MysqlObj.writeStatus("success",IsWaterMark,IsOverWrite,info="Successfully process the file!")
    if IsOverWrite:
        StoWebHdfs.remove(BakcupPathHdfs_NEW)
        RedisObj = baseclass.interWithRedis(logger,vid)
        RedisObj.WriteUrlToCacheList("cacheurl_list","/%s/%s"%(uid,vid))
        if StoWebHdfs.status == 200:
            logger.info("Successfully delete the backup directory")
        else:
            logger.info("WARNING: Failed to detele the backup directory!")


#删除web端原始视频文件
RunCmdObj.run(["rm -f %s"%VideoFilePath],QuitFlag=False)

#清理临时文件
RunCmdObj.run(["rm -rf /tmp/%s/"%(info_dict['name'])])

#删除mapreducer集群中中间数据
MapWebHdfs.remove("/%s" % vid)

logger.info("Video file %s.%s handle complete \n\n"%(vid,OriginVideoFormat))

