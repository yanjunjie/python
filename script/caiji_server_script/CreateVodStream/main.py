#!/usr/bin/env python
# -*- encoding:utf-8 -*-

# ------------------------------------------------ /
# Purpose:
#       Generate vod video streaming for a user-specified
#+      time period
# @author: wye
# @date: 2014-09-10
# @achieve basic functions
# @date: 2015-10-03
# @redefine the vod handle status,the following.
# @######################
#  -1  ---  还没处理      
#   0  ---  正在处理
#   1  ---  处理失败
#   2  ---  处理成功
#  11  ---  ts.txt不能找到即存在ts文件但都不符合要求
#  12  ---  不能找到直播流目录或目录存在但其中没有任何ts文件
# @#######################
# @date:2015-12-18
# @With the attendance machine binding cameras don't delete the original 
# +TS file after on vod generated
# @#######################
# @date:2016-05-03
# @Fix bug on vod processing failed but don't delete temporary file
# ------------------------------------------------ /

import os
import sys
import glob
import time
import redis
import ujson
import string
import random
import datetime
import subprocess
import ConfigParser
from PubMod import GetLog
from PubMod import runCmd
from PubMod import SendMail
from PubMod import DataInter
from PubMod import TsIsVaild
from PubMod import GetAvgbrAndAvgtime
from PubMod import CustomVodException
from WebHDFSApi import WebHadoop

class VodStream(object):
    
    def __init__(self,logger,cids=None,date=None):
        
        self.logger = logger
        self.ScriptHome = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.config = ConfigParser.ConfigParser()
        self.config.read(os.path.dirname(os.path.abspath(sys.argv[0]))+"/config.ini")
        
        self.FFMPEG = self.config.get("main", "FFMPEG")
        self.FFPROBE = self.config.get("main","FFPROBE")
        
        self.HDFSInterfaces = self.config.get("HDFS","HDFSInterfaces")
        self.HDFSInterfacePort = self.config.get("HDFS","HDFSInterfacePort")
        self.HDFSUser = self.config.get("HDFS","HDFSUser")
        
        self.ExeShellCmdObj=runCmd(self.logger)
        self.DataInterObj = DataInter(self.logger)
                
        if cids != None and date != None:
            self.CidsList = cids.split(",")
            self.date = date
        elif cids == None and date == None:
            self.CidsList = self.GetRunInLocalCids()
            # -------------------- /
            # 在凌晨00,01时段,跑前一天未跑的点播任务
            # -------------------- /
            if datetime.datetime.now().strftime("%H") in ["00","01"]:
                self.date = (datetime.datetime.now()-datetime.timedelta(days=1)).strftime("%Y%m%d")
            else:
                self.date = datetime.datetime.now().strftime("%Y%m%d")
                #self.date = (datetime.datetime.now()-datetime.timedelta(days=1)).strftime("%Y%m%d")
            # -------------------- /
            # 在凌晨02,03时段,清除前一天到期的HDFS端点播文件和数据库相关记录
            # -------------------- /
            if datetime.datetime.now().strftime("%H") in ["02","03"]:
                PreDate = (datetime.datetime.now()-datetime.timedelta(days=1)).strftime("%Y%m%d")
                self.DataInterObj.DelExpireVod(PreDate)        
            # -------------------- /
            # 在晚上20,21时段,清除前一天在采集服务器本地生成的直播流文件
            # -------------------- /
            if datetime.datetime.now().strftime("%H") in ["20","21"]:
                PreDate = (datetime.datetime.now()-datetime.timedelta(days=1)).strftime("%Y%m%d")       
                self.DelLocalLiveDir(PreDate)
            # -------------------- /
            # 在晚上22,23时段,在MYSQL删除两天前处理失败的点播记录即handlestatus=0的记录
            # -------------------- /
            if datetime.datetime.now().strftime("%H") in ["22","23"]:
                PreTwoDate = (datetime.datetime.now()-datetime.timedelta(days=2)).strftime("%Y%m%d")
                self.DelFailVodRecordFromMysql(PreTwoDate)
        else:
            self.logger.error("Parameter specifies incorrect,quit!!!")
            sys.exit()
    
    # ------------------------------- /
    # 从采集服务器本地获取运行在本服务器的摄像头CID列表
    # ------------------------------- /
    
    def GetRunInLocalCids(self):
        CidsInLocalFile = self.config.get("main","CidsInLocalFile")
        self.ExeShellCmdObj.run(["/bin/bash %s/ScanLocalCidsFile.sh %s"%(self.ScriptHome,CidsInLocalFile)])
        CidsStr = self.ExeShellCmdObj.stdout[0].strip('\n')
        CidsList = CidsStr.split(",")

        self.logger.info("All Cids : %s"%CidsList)  
        RunningCidsList = []
        for cid in CidsList:
            CamStatus = self.DataInterObj.GetCamDBStatus(cid)
            self.logger.info("cid:%s,status:%s"%(cid,CamStatus))
       	    if CamStatus == 1:
                RunningCidsList.append(cid)
                self.CheckDaemonProcess(cid)
        self.logger.info("Running Cids :%s"%RunningCidsList)

        return RunningCidsList

    # ------------------------------- /
    # 摄像头设置是启动的，检查相应daemon进程是否存在于采集流服务器
    # ------------------------------- /
    def CheckDaemonProcess(self,cid):  
        ptmp1 = subprocess.Popen("/bin/ps -aux | grep %s | grep -v grep | grep ffstart | wc -l"%cid,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        DaemonNum= int(ptmp1.stdout.read())
        if DaemonNum != 1:
            MailObj = SendMail(self.logger,"ffstart daemon process exception","%s"%cid)
            MailObj.start()
    
    # ------------------------------- /
    # 点播计划结束时间与开始时间之间相隔的秒数
    # ------------------------------- /
    
    def CalVodTimeLength(self,vod):
        seglist = vod.split("-")
        VodStartTimeHour = int(seglist[0].split(":")[0])
        VodStartTimeMinutes = int(seglist[0].split(":")[1])
        VodEndTimeHour = int(seglist[1].split(":")[0])
        VodEndTimeMinutes = int(seglist[1].split(":")[1])
        VodTimeLength = VodEndTimeHour*3600+VodEndTimeMinutes*60 - VodStartTimeHour*3600 - VodStartTimeMinutes*60
        return VodTimeLength
      
    # ------------------------------- /
    # 返回待处理的点播计划列表
    # 列表元素格式:08:15-09:05-erth-7-20140910-12kb22-Cvvvlv22-Y4h318142dV
    # ------------------------------- /
    
    def GenPendingVodList(self):
        weekday = str(time.strptime(self.date,"%Y%m%d").tm_wday+1)
        TimeStampNow = int(time.time())
        NeedGenVodList = []
        #扫描在该服务器运行的每个CID,获取今天要生成的点播信息。
        for cid in self.CidsList:
            OidRidandVodsavedays = self.DataInterObj.GetOidRidandVodsavedays(cid)
            if OidRidandVodsavedays != None:
                VodPlanRawData = self.DataInterObj.GetCidVodPlan(cid)
                #self.logger.info("Vod Plan Raw Data : \n %s"%VodPlanRawData)
                if VodPlanRawData != None:
                    VodPlanDict = ujson.decode(VodPlanRawData)
                    if VodPlanDict.has_key(weekday) == True:
                        VodPlanWdayStr = VodPlanDict[weekday]
                        VodPlanWdayList = VodPlanWdayStr.strip("{").strip("}").split(",")
                        for vod in VodPlanWdayList:
                            #取点播结束时间
                            VodEndTime = vod.split("-")[1]
                            #点播结束时间格式转换,08:15->08:15:00
                            VodEndTime = VodEndTime + ":00"
                            #继续规范点播结束时间
                            if VodEndTime == "24:00:00":VodEndTime = "23:59:59"
                            #获取该点播结束时间时间戳
                            YmdHMSTime_VodEndTime = self.date + " " + VodEndTime
                            TimeStamp_VodEndTime = int(time.mktime(time.strptime(YmdHMSTime_VodEndTime, "%Y%m%d %H:%M:%S")))
                            #点播结束时间戳小于程序开始时的时间戳,就加入待处理队列.
                            #队列元素格式例:08:15-09:05-erth-7-20140910-12kb22-Cvvvlv22-Y4h318142dV
                            if TimeStampNow >= TimeStamp_VodEndTime:
                                vod = vod + "-" + str(OidRidandVodsavedays[1]) + "-" + str(self.date) + "-" + str(OidRidandVodsavedays[0]) + "-" + cid + "-" + str(OidRidandVodsavedays[2])
                                NeedGenVodList.append(vod)
                    else:
                        self.logger.info("The camera %s no have any vod plan today"%cid)
                        continue
                else:
                    self.logger.info("Can't find %s vod key in redis , Have two reasons , One is only have live course , Two is generate vod key failure."%cid)
                    #MailObj = SendMail(self.logger,"Vod Plan No Exist In Redis","%s"%cid)
                    #MailObj.start()
                    continue
                   
        if len(NeedGenVodList) == 0:
            self.logger.info("There is no vod plan handle at the moment")
            sys.exit()
        #self.logger.info("Pending Handle Vod Plan for all cids in local server,Print follow (unsort),\n %s"%NeedGenVodList)
        #按每个点播计划时间长短，对待处理队列重新排序,新队列按照时长从小往大排,以便先处理时长短的点播计划.
        NeedGenVodSortList = []
        while True:
            try:
                vod1 = NeedGenVodList[0]
            except IndexError:
                break
            VodTimeLength = self.CalVodTimeLength(vod1)
            TmpVod = vod1
            TmpVodTimeLength = VodTimeLength         
            for vod in NeedGenVodList:
                VodTimeLength = self.CalVodTimeLength(vod)
                if VodTimeLength < TmpVodTimeLength:
                    TmpVod = vod
                    TmpVodTimeLength = VodTimeLength
            NeedGenVodList.remove(TmpVod)
            NeedGenVodSortList.append(TmpVod)
        #self.logger.info("Pending Handle Vod Plan for all cids in local server,Print follow (sort),\n %s"%NeedGenVodSortList)        
        return NeedGenVodSortList
    
    # ------------------------------- /
    # 检查待处理队列中点播计划状态,没被处理或先前处理失败？的会被重新处理
    # ------------------------------- /
               
    def GenVodStream(self):
        PendingVodList = self.GenPendingVodList()
        for vod in PendingVodList:
            self.logger.info("Prepare handle vod plan : %s"%vod)
            HandleStatus = self.DataInterObj.GetVodHandleStatus(vod)
            VodHandleFlagStr = ''.join(random.sample(string.ascii_letters + string.digits,8))
            if HandleStatus == 0 or HandleStatus == 2:
                self.logger.info("The vod plan(%s),Are being handling or have been handle successfully!!!,Discard it,Continue to handle other's vod plan"%vod)
            elif HandleStatus == 1:
                self.logger.info("The Vod plan have been hanedled,but it handle fail,Into core module Rehandle it")
                self.DataInterObj.UpdateVodHandleStatus(vod,0)
                try:
                    self.GenVodStreamCoreMod(vod,VodHandleFlagStr)
                except Exception as e:
                    TmpDirName = "VodHandle_" + VodHandleFlagStr
                    self.TheLastThing(TmpDirName)
                    if e.flag == "TsTxtNoExist":
                        #Ts.txt No Exist
                        self.DataInterObj.UpdateVodHandleStatus(vod,11)
                        continue
                    if e.flag == "LiveStreamDirNoExist":
                        #Live Stream Dir No Exist Or No Ts File In Dir
                        self.DataInterObj.UpdateVodHandleStatus(vod,12)
                        continue
                    if e.flag == "ExecShellCmdFail":
                        #Exec Shell Cmd Fail
                        self.DataInterObj.UpdateVodHandleStatus(vod,1)
                        continue
            elif HandleStatus == -1:
                self.logger.info("The vod plan has not been handle,Into core module handle it")
                self.DataInterObj.InsertVodHandleStatus(vod,0)
                try:
                    self.GenVodStreamCoreMod(vod,VodHandleFlagStr)
                except Exception as e:
                    TmpDirName = "VodHandle_" + VodHandleFlagStr
                    self.TheLastThing(TmpDirName)
                    if e.flag == "TsTxtNoExist":
                        #Ts.txt No Exist
                        self.DataInterObj.UpdateVodHandleStatus(vod,11)
                        continue
                    if e.flag == "LiveStreamDirNoExist":
                        #Live Stream Dir No Exist Or No Ts File In Dir
                        self.DataInterObj.UpdateVodHandleStatus(vod,12)
                        continue
                    if e.flag == "ExecShellCmdFail":
                        #Exec Shell Cmd Fail
                        self.DataInterObj.UpdateVodHandleStatus(vod,1)
                        continue
            elif HandleStatus == 11 or HandleStatus == 12:
                self.logger.info("The vod plan : %s , handle status is 11 or 12"%vod)
            else:
                self.logger.error("The vod plan : %s handlestatus error,quit"%vod)
                sys.exit()
    
    # ------------------------------- /
    # 点播计划处理核心模块
    # ------------------------------- /
    
    def GenVodStreamCoreMod(self,vod,VodHandleFlagStr):
        VodSplitList = vod.split("-")
        
        self.oid = VodSplitList[5]
        self.cid = VodSplitList[6]
        self.VodDate = VodSplitList[4]
        
        VodStartTime = VodSplitList[0]
        VodEndTime =  VodSplitList[1]
        
        VodStartTimeStr = VodStartTime.split(":")[0] + VodStartTime.split(":")[1] 
        VodEndTimeStr = VodEndTime.split(":")[0] + VodEndTime.split(":")[1] 

        self.M3u8FileName = str(self.VodDate)+str(VodStartTimeStr)+str(VodEndTimeStr)+".m3u8"
        self.PrePicFileName = str(self.VodDate)+str(VodStartTimeStr)+str(VodEndTimeStr)+".jpg"
        
        VodTsDir = self.config.get("main","DataRootDir")+"/"+self.oid+"/"+self.cid+"/media/"+self.VodDate
        OriVodTsDir = VodTsDir
        
        #检查是否存在需要处理的直播流目录和该目录下是否有文件.
        if os.path.isdir(VodTsDir) == True and len(glob.glob(VodTsDir+"/*.ts")) > 0:
            self.logger.info("Live stream dir is meet the handle requirements")
            
            #随机采样获取平均码率和时长
            TsAvgbr,TsAvgtime = GetAvgbrAndAvgtime(VodTsDir,self.VodDate,self.logger,self.FFPROBE)
            
            #检查点播开始与结束区间TS文件是否有缺失
            VodStartTsNum = int(VodStartTime.split(":")[0])*360 + int(VodStartTime.split(":")[1])*6 + 1
            VodEndTsNum = int(VodEndTime.split(":")[0])*360 + int(VodEndTime.split(":")[1])*6
            IdealTsNum = VodEndTsNum - VodStartTsNum + 1
            RealTsNum = 0
            TmpDirName = "VodHandle_" + VodHandleFlagStr
            self.ExeShellCmdObj.run(["mkdir -p /tmp/%s"%TmpDirName])
            
            for i in range(IdealTsNum):
                TsNum = VodStartTsNum + i
                VodTsName = self.VodDate+"%05d"%TsNum+".ts"
                VodTsPath = VodTsDir+"/"+VodTsName
                if TsIsVaild(VodTsPath,TsAvgbr,TsAvgtime,self.FFPROBE,self.logger) == True:
                    RealTsNum = RealTsNum + 1
                    self.ExeShellCmdObj.run(["echo %s >> /tmp/%s/ts.txt"%(VodTsName,TmpDirName)])
                else:
                    self.logger.warning("TS file : %s ,Does not meet the handle conditions"%VodTsPath)
                    
            #比较理想状态下和实际状况下TS文件个数
            self.logger.info("Ideal TS Num is : %s,Real TS num is : %s"%(IdealTsNum,RealTsNum))
            if IdealTsNum == RealTsNum:
                #生成M3U8文件
                self.GenM3u8File(VodTsDir,VodStartTsNum,IdealTsNum)
                #生成预览图
                self.GenPrePic(VodTsDir,VodStartTsNum)
                #上传所有文件到HDFS
                self.UploadFileToHDFS(VodTsDir,VodStartTsNum,IdealTsNum)
            else:
                SplitSegList =  self.TsTxtSplitSeg(TmpDirName)
                #合并为多个小mp4文件,然后小mp4文件转化为小TS文件
                z = 1
                TmpTsStr = ""
                for seg in SplitSegList:
                    cmd = "cd %s &&"
                    cmd = cmd + "%s -d -y -i concat:'%s' -c copy -absf aac_adtstoasc /tmp/%s/output%s.mp4 &&"
                    cmd = cmd + "cd /tmp/%s &&"
                    cmd = cmd + "%s -d -i output%s.mp4 -c copy -bsf:v h264_mp4toannexb -f mpegts output%s.ts"
                    cmdstr = cmd%(VodTsDir,self.FFMPEG,seg,TmpDirName,z,TmpDirName,self.FFMPEG,z,z)
                    self.ExeShellCmdObj.run([cmdstr])
                    TmpTsStr = TmpTsStr + "|" + "output%s.ts"%z
                    z = z + 1
                #多个小TS文件合并为一个大的mp4文件
                TmpTsStr = TmpTsStr.strip("|")
                cmd = "cd /tmp/%s &&"
                cmd = cmd + "%s -d -y -i concat:'%s' -c copy -bsf:a aac_adtstoasc output.mp4"
                cmdstr = cmd%(TmpDirName,self.FFMPEG,TmpTsStr)      
                self.ExeShellCmdObj.run([cmdstr])
                #大mp4文件转化为ts文件
                cmd = "cd /tmp/%s &&"
                cmd = cmd + "%s -d -i output.mp4 -acodec copy -vcodec copy -bsf:v h264_mp4toannexb -f mpegts output.ts"
                cmdstr = cmd%(TmpDirName,self.FFMPEG)
                self.ExeShellCmdObj.run([cmdstr])
                #分割大ts文件
                cmd = "cd /tmp/%s &&"
                cmd = cmd + "mkdir ts &&"
                cmd = cmd + "%s -d -i output.ts -vcodec copy -acodec copy -map 0 -f segment -segment_time_delta 0.5  -segment_time 10 -segment_start_number %s -segment_list outputold.m3u8 -segment_list_type m3u8 -segment_format mpegts /tmp/%s/ts/%s" 
                cmdstr = cmd%(TmpDirName,self.FFMPEG,VodStartTsNum,TmpDirName,self.VodDate)
                cmdstr = cmdstr + "%05d.ts"
                self.ExeShellCmdObj.run([cmdstr]) 
                #生成M3U8文件
                VodTsNum = len(glob.glob("/tmp/%s/ts/*.ts"%TmpDirName))
                VodTsDir = "/tmp/%s/ts"%TmpDirName
                self.GenM3u8File(VodTsDir,VodStartTsNum,VodTsNum)
                #生成预览图
                self.GenPrePic(VodTsDir,VodStartTsNum)
                #上传所有文件到HDFS
                self.UploadFileToHDFS(VodTsDir,VodStartTsNum,VodTsNum)
            #更新数据库点播处理状态
            self.DataInterObj.UpdateVodHandleStatus(vod,2)
            #删除点播生成成功的ts文件,释放硬盘空间
            self.DelVodTsFiles(OriVodTsDir,TmpDirName,self.cid)
            #收尾处理
            self.TheLastThing(TmpDirName)                      
        else:
            self.logger.error("Live stream dir is not exist or is null ,Can't meet handle requirement!!!")
            raise CustomVodException("LiveStreamDirNoExist","Live stream dir is not exist or is null")
                       
    def TsTxtSplitSeg(self,TmpDirName):
        if os.path.isfile("/tmp/%s/ts.txt"%TmpDirName):
           self.ExeShellCmdObj.run(["cat /tmp/%s/ts.txt"%TmpDirName])
           RawDataList = self.ExeShellCmdObj.stdout                             
           i = 0
           TmpSeg = ""
           SplitSeg = []
           for j in RawDataList:
               j = j.strip('\n')
               TmpSeg = TmpSeg + j + "|"
               i = i + 1
               if i > 360:
                   TmpSeg = TmpSeg.strip("|")
                   SplitSeg.append(TmpSeg)
                   i = 0
                   TmpSeg = ""
           TmpSeg = TmpSeg.strip("|")
           SplitSeg.append(TmpSeg)
           return SplitSeg
        else:
           self.logger.error("/tmp/%s/ts.txt file not exist,quit"%(TmpDirName))
           raise CustomVodException("TsTxtNoExist","ts.txt file not exist")
    
    # ------------------------------- /
    # 生成M3U8文件
    # ------------------------------- / 
            
    def GenM3u8File(self,VodTsDir,VodStartTsNum,VodTsNum):
        MaxDuration = 10
        M3u8FilePath = VodTsDir + "/" + self.M3u8FileName

        #@ If the m3u8 file exist,Empty it.
        cmd = ": > %s"%M3u8FilePath
        self.ExeShellCmdObj.run([cmd])

        for i in range(VodTsNum):
            TsNum = VodStartTsNum + i
            VodTsName = self.VodDate+"%05d"%TsNum+".ts"
            VodTsPath = VodTsDir+"/"+VodTsName
            self.ExeShellCmdObj.run(["%s -v quiet -show_format -print_format json %s"%(self.FFPROBE,VodTsPath)],StdoutFlag="read")
            TsMetaData = ujson.decode(self.ExeShellCmdObj.stdout)["format"]
            if TsMetaData.has_key("duration"):
               TsDuration = TsMetaData["duration"]
            else:
               continue 
            if float(TsDuration) > MaxDuration:MaxDuration = float(TsDuration)
            # ----------------------------------- /
            # 生成M3U8文件中间部分,形如:
            # #EXTINF:10.000000,
            # 2014090602161.ts
            # ----------------------------------- /
            cmd = "echo \"#EXTINF:%s,\" >> %s && echo \"%s\" >> %s"%(TsDuration,M3u8FilePath,VodTsName,M3u8FilePath)
            self.ExeShellCmdObj.run([cmd])
        # ---------------------------------------- /
        # 生成M3U8文件头部分,形如:
        # #EXTM3U
        # #EXT-X-VERSION:3
        # #EXT-X-MEDIA-SEQUENCE:2161
        # #EXT-X-ALLOW-CACHE:YES
        # #EXT-X-TARGETDURATION:10
        # ---------------------------------------- /
        cmd = "sed -i \"1i #EXTM3U\"  %s &&"
        cmd = cmd + "sed -i \"2i #EXT-X-VERSION:3\"  %s &&"
        cmd = cmd + "sed -i \"3i #EXT-X-MEDIA-SEQUENCE:%s\" %s &&"
        cmd = cmd + "sed -i \"4i #EXT-X-ALLOW-CACHE:YES\"  %s &&"
        cmd = cmd + "sed -i \"5i #EXT-X-TARGETDURATION:%s\"  %s"
        cmdstr = cmd%(M3u8FilePath,M3u8FilePath,0,M3u8FilePath,M3u8FilePath,int(MaxDuration),M3u8FilePath)
        self.ExeShellCmdObj.run([cmdstr])
        # --------------------------------------- /
        # 生成M3U8文件尾部,形如：
        # #EXT-X-ENDLIST
        # --------------------------------------- /
        cmd = "sed -i \'$a #EXT-X-ENDLIST\' %s "%M3u8FilePath
        self.ExeShellCmdObj.run([cmd])
        
    # ------------------------------ /
    # 生成预览图,第三秒开始第一帧.
    # ------------------------------ /    
        
    def GenPrePic(self,VodTsDir,VodStartTsNum):
        PrePicFilePath = VodTsDir + "/" + self.PrePicFileName
        VodFirstTsName = self.VodDate+"%05d"%VodStartTsNum+".ts"
        VodFirstTsPath = VodTsDir+"/"+VodFirstTsName
        self.ExeShellCmdObj.run(["%s -y -i %s -vframes 1 -ss 00:00:03 %s"%(self.FFMPEG,VodFirstTsPath,PrePicFilePath)])    
        
    # ------------------------------ /
    # 上传M3U8文件,预览图,TS文件到HDFS
    # ------------------------------ /    
        
    def UploadFileToHDFS(self,VodTsDir,VodStartTsNum,VodTsNum):
        PrePicFilePath = VodTsDir + "/" + self.PrePicFileName
        M3u8FilePath = VodTsDir + "/" + self.M3u8FileName
        #DebugLog = GetLog(self.cid+"_"+self.M3u8FileName.split(".")[0])
        self.logger.info("Prepare upload File to hdfs,File in dir is : %s"%VodTsDir)
        if os.path.isfile(M3u8FilePath) and os.path.isfile(PrePicFilePath) and len(glob.glob(VodTsDir+"/*.ts")) != 0:
            WebHdfsObj = WebHadoop(self.HDFSInterfaces,self.HDFSInterfacePort,self.HDFSUser,self.logger)
            HdfsTsSaveDir = "/vod/%s/%s/%s"%(self.oid,self.cid,self.VodDate)
            if WebHdfsObj.mkdir(str(HdfsTsSaveDir)) == True:
                self.logger.info("Create dir %s in hdfs success!!!"%HdfsTsSaveDir)
                #上传TS文件到HDFS
                for i in range(VodTsNum):
                    TsNum = VodStartTsNum + i
                    VodTsName = self.VodDate+"%05d"%TsNum+".ts"
                    VodTsPath = VodTsDir+"/"+VodTsName
                    HdfsTsSavePath = "/vod/%s/%s/%s/%s"%(self.oid,self.cid,self.VodDate,VodTsName)     
                    WebHdfsObj.put_file(str(VodTsPath),str(HdfsTsSavePath),overwrite="true")                               
                #上传m3u8文件到HDFS
                HdfsM3u8SavePath = "/vod/%s/%s/%s/%s"%(self.oid,self.cid,self.VodDate,self.M3u8FileName)
                WebHdfsObj.put_file(str(M3u8FilePath),str(HdfsM3u8SavePath),overwrite="true")      
                #上传预览图到HDFS
                HdfsPrePicSavePath = "/vod/%s/%s/%s/%s"%(self.oid,self.cid,self.VodDate,self.PrePicFileName)
                WebHdfsObj.put_file(str(PrePicFilePath),str(HdfsPrePicSavePath),overwrite="true") 
            else:
                self.logger.error("Create dir %s in hdfs fail,quit!!!"%HdfsTsSaveDir)
                sys.exit()                                 
        else:
            self.logger.error("Upload condiition is not satisfied,quit!!!")
            sys.exit()
    
    # ------------------------------ /
    # 删除前一天的直播文件目录
    # ------------------------------ /
    def DelLocalLiveDir(self,date):
        DataRootDir = self.config.get("main","DataRootDir")
        PendingDelDirList = glob.glob("%s/*/*/*/%s"%(DataRootDir,date))
        if len(PendingDelDirList) != 0:
            for dir in PendingDelDirList:
                self.ExeShellCmdObj.run(["rm -rf %s"%dir],QuitFlag=False)
    
    # ------------------------------ /
    # 点播生成成功,删除该点播原始ts文件,释放硬盘空间.
    # 但如果该摄像头和考勤机绑定将不执行该动作.
    # ------------------------------ /
    def DelVodTsFiles(self,VodTsDir,TmpDirName,cid):
        if self.DataInterObj.GetCidIsBindKQ(cid) == False:
            self.ExeShellCmdObj.run(["cd %s && cat /tmp/%s/ts.txt | xargs rm -f"%(VodTsDir,TmpDirName)])

    # ------------------------------ /
    # 清除临时文件.
    # ------------------------------ /
    def TheLastThing(self,TmpDirName):
        cmd = "rm -rf /tmp/%s"%TmpDirName
        self.ExeShellCmdObj.run([cmd])
               
if __name__ == "__main__":
    logger = GetLog("GenVod")
    try:
        logger.info("********************************************************")
        logger.info("              Start Handle Vod Plan                     ")
        logger.info("********************************************************")
        VodStream(logger).GenVodStream()
    except Exception,e:
        logger.error("Main program run exception,error is %s"%e)
        sys.exit()
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
