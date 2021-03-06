#!/usr/bin/env python
# -*- encoding:utf-8 -*-

#########################################
# Purpose:
#       this is daemon process for send cameras
#+      status info to carbon,in order to draw a state
#+      diagram in graphite.
# 
# Write  by wye in 2014.08.18
# Copyright@2014 cloudiya technology
##########################################

import os
import sys
import time
import socket
import fcntl
import struct
import syslog
import MySQLdb
import subprocess


# --/
#    获取本采集服务器IP地址
# --/

def _ifinfo(sock, addr, ifname):
    iface = struct.pack('256s', ifname[:15])
    info = fcntl.ioctl(sock.fileno(), addr, iface)
    if addr == 0x8927:
        hwaddr = []
        for char in info[18:24]:
            if len(hex(ord(char))[2:]) == 1:
                str = (hex(ord(char))[2:]*2).upper()
            else: 
                str = (hex(ord(char))[2:]).upper()
            hwaddr.append(str)
        return ':'.join(hwaddr)
    else:
        return socket.inet_ntoa(info[20:24])

def ifconfig(ifname):
    ifreq = {'ifname': ifname}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        ifreq['addr'] = _ifinfo(sock, 0x8915, ifname) # SIOCGIFADDR
        ifreq['brdaddr'] = _ifinfo(sock, 0x8919, ifname) # SIOCGIFBRDADDR
        ifreq['netmask'] = _ifinfo(sock, 0x891b, ifname) # SIOCGIFNETMASK
        ifreq['hwaddr'] = _ifinfo(sock, 0x8927, ifname) # SIOCSIFHWADDR
    except:
        pass
    sock.close()
    return ifreq['addr']


class SendCamStaToMonServer():
    
    def __init__(self):
        
        self.CidRestartTimePoint = {}
        self.CidList = []
        self.WriteDBInfo = {}
        
        self.CidsNameFile = "/opt/caiji/script/vodconfig"
        self.CARBON_SERVER = "10.1.0.254"
        self.CARBON_PORT = 2003
        self.delay = 60
        
        self.ServerIPAddr = "_".join(ifconfig("eth0").split("."))
        
        self.MysqlServer = "10.1.0.4"
        self.MysqlUser = "cloudiya"
        self.MysqlPwd = "c10udiya"
        self.DataBase = "68baobao"
        self.Table = "t_device"
        
    # -- /
    #     得到运行在本采集服务器的Cameras的cid
    # -- /
    def GetCidList(self):
        syslog.openlog("MonitorCamStatus") 
        self.CidList = ["Cc83Vp25","CGYIOd25","ClGAvF25","CC0yGa02","CCBhqC02"]
        """       
        if os.path.exists(self.CidsNameFile):
            file = open(self.CidsNameFile)
            lines = file.readlines()
            for line in lines:
                line = line.strip()
                self.CidList.append(line)
        else:
            syslog.syslog("NO Find The File For Save Cids Name In %s"%self.CidsNameFile)
        """
    
    # --/
    #    修改摄像头状态
    # --/
    def ModifyCamStatus(self,cid,status):
        SuccFlag = True
        try:
            dbconn = MySQLdb.connect(host=self.MysqlServer,user=self.MysqlUser,passwd=self.MysqlPwd)
            dbcursor = dbconn.cursor()
            dbconn.select_db(self.DataBase)
            dbcursor.execute('update t_device set status=%s where index_code=%s',(status,cid))
            dbconn.commit()
        except Exception,e:
            print e
            syslog.openlog("MonitorCamStatus")
            syslog.syslog("Write status to mysql fail,the next cycle will try to write again!")
            SuccFlag = False
            
        self.WriteDBInfo[cid]["flag"] = SuccFlag
    
    def IsWriteInfoToDB(self,cid,status):
        if self.WriteDBInfo.has_key(cid):
            OldFlag = self.WriteDBInfo[cid]["flag"]
            OldStatus = self.WriteDBInfo[cid]["status"]
            if OldStatus == status:
                if OldFlag == False:
                    self.ModifyCamStatus(cid,status)
            else:
                self.WriteDBInfo[cid]["status"] = status
                self.ModifyCamStatus(cid,status)
        else:
            self.WriteDBInfo[cid] = {"status":status,"flag":False}
            self.ModifyCamStatus(cid,status)
    
    # -- /
    #     获取进程相关信息
    # -- /
    def GetCamStatusInfo(self,cid):
        # --/
        #
        #     Camera进程状态值
        #     0 -- Living
        #     1 -- WaitLiving Or Fault
        #     2 -- No Find Any Related Process
        #     3 -- Only Have FFmpeg Process
        #     4 -- Other Fault
        #
        # --/
        ptmp1 = subprocess.Popen("/bin/ps -aux | grep %s | grep -v grep | grep ffstart | wc -l"%cid,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        DaemonNum= int(ptmp1.stdout.read())
        ptmp2 = subprocess.Popen("/bin/ps -aux | grep %s | grep -v grep | grep ffmpeg | wc -l"%cid,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        FfmpegNum = int(ptmp2.stdout.read())
        if DaemonNum == 1 and FfmpegNum == 1:
            CamStatus = 0
            CamPhpStatus = 1
        elif DaemonNum == 1 and FfmpegNum == 0:
            CamStatus = 1
            CamPhpStatus = 2
        elif DaemonNum == 0 and FfmpegNum == 0:
            CamStatus = 2
            CamPhpStatus = 3
        elif DaemonNum == 0 and FfmpegNum == 1:
            CamStatus = 3
            CamPhpStatus = 3
        else:
            CamStatus = 4
            CamPhpStatus = 3
        
        # --/
        #       
        #     Camera FFmpeg进程重启状况
        #     0 -- No Restart The Scan Interval
        #     1 -- Have Restart The Scan Interval
        #     2 -- No Exist The Camera FFmpeg Process For The Cid
        #
        # --/
        if CamStatus == 0 or CamStatus == 3:
            ptmp3 = subprocess.Popen("/bin/ps -aux | grep %s | grep -v grep | grep ffmpeg | awk '{print $2}'"%cid,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)    
            pid = ptmp3.stdout.read()
            if self.CidRestartTimePoint.has_key(cid):
                if self.CidRestartTimePoint[cid] == pid:
                    CamRestartStatus = 0
                else:
                    CamRestartStatus = 1
                    self.CidRestartTimePoint[cid] = pid
            else:
                CamRestartStatus = 0
                self.CidRestartTimePoint[cid] = pid
        else:
            CamRestartStatus = 2
                   
        return CamStatus,CamRestartStatus,CamPhpStatus
    
    # -- / 
    #      依次扫描本服务器每一个Camera的状态
    # -- /
    def ScanCidsAndSendInfo(self):
        syslog.openlog("MonitorCamStatus")
        sock = socket.socket()
        try:
            sock.connect( (self.CARBON_SERVER,self.CARBON_PORT))
        except:
            syslog.syslog("Couldn't connect to %s on port %s"%(self.CARBON_SERVER,self.CARBON_PORT))
            sys.exit(1)
        while True:
            self.GetCidList()
            now = int(time.time())
            WaitSendInfo = []
            if len(self.CidList) != 0:
                for cid in self.CidList:
                    CamStatus,CamRestartStatus,CamPhpStatus = self.GetCamStatusInfo(cid)
                    WaitSendInfo.append("%s.Camera.%s.CamStatus %s %d"%(self.ServerIPAddr,cid,CamStatus,now))
                    WaitSendInfo.append("%s.Camera.%s.CamRestartStatus %s %d"%(self.ServerIPAddr,cid,CamRestartStatus,now))
                    self.IsWriteInfoToDB(cid,CamPhpStatus)
                message = '\n'.join(WaitSendInfo) + '\n'
                sock.sendall(message)
                time.sleep(self.delay)

    # --/
    #     主程序
    # --/
    def main(self):
        self.ScanCidsAndSendInfo()

######################################################################                        
if __name__ == "__main__":
    try: 
        pid = os.fork() 
        if pid > 0:
            # exit first parent
            sys.exit(0) 
    except OSError, e: 
        print >>sys.stderr, "fork #1 failed: %d (%s)" % (e.errno, e.strerror) 
        sys.exit(1)
    # decouple from parent environment
    os.chdir("/")
    os.setsid() 
    os.umask(0) 
    # do second fork
    try: 
        pid = os.fork() 
        if pid > 0:
            # exit from second parent, print eventual PID before
            #print "Daemon PID %d" % pid 
            sys.exit(0) 
    except OSError, e: 
        print >>sys.stderr, "fork #2 failed: %d (%s)" % (e.errno, e.strerror) 
        sys.exit(1) 
    # start the daemon main loop
    SendCamStaToMonServer().main()
    
