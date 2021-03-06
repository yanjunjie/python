#! /usr/bin/env python
# -*- encoding:utf-8 -*-

# --------------------------------------- /
#Created on 2015-10-19
#author: wye
#Copyright @ 2014 - 2015  Cloudiya Tech . Inc
#
#Purpose:
#  Attendance Admin Platform API Interface.
#@date:2015-10-19
#@Achieve basic functions,Build version v1.0
#@date:2015-11-30
#@Save Parameters To ROM 
#@date:2016-01-18
#@add command for get attendance device config parameter 
#@date:2016-01-26
#@increased support for multiple antennas
# --------------------------------------- /


from bottle import Bottle,run
from socket import *
from time import time
import binascii
import struct
import sys
import os
import re

#######################
# Admin Platform Api to Server Commands
#######################

#@Reboot Controller To Specified Device
cmd_admin_reboot_reader = "cc01" # 0xcc01 

#@Sync Server Time To Specified Device
cmd_admin_sync_time  = "cc02" # 0xcc02

#@Reset System Parameter
cmd_admin_set_net_para = "cc03" #0xcc03

#@Send Command To Device For Get Config Parameter
cmd_admin_get_conf_para = "cc04" #0xcc04

# #@Set Heartbeat Packet Interval To Specified Device
# cmd_admin_set_heartbeat_interval = "cc04" #0xcc04

# #@Set Antenna Power To Specified Device
# cmd_admin_antenna_power = "cc05" #0xcc05        

# #@Set Reader SerialID To Specified Device
# cmd_admin_set_reader_serialid = "cc06" #0xcc05  


#@Send Binary Data To Server
def SendBinDataToServer(BinaryData):
    bufsize = 1024
    host = "61.183.254.135"
    port = 5005
    addr = (host,port)
    client_sock = socket(AF_INET,SOCK_STREAM)
    client_sock.connect(addr)
    client_sock.send(BinaryData)
    client_sock.close()


#@Conversion IP For The Specified format
def ConIPFormat(IPAddr):
    if re.match('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$',IPAddr) == None:
        return None
    else:
        ascii_str = "" 
        FieldList = IPAddr.split(".")
        for Field in FieldList:
            s = struct.pack('<B',int(Field))
            ascii_str = ascii_str + binascii.b2a_hex(s)
        ascii_str = ascii_str.strip()
        return ascii_str
 
app = Bottle()

#@Reboot Attendacen Device Controller 
@app.route('/kqdevapi/reboot/<SerialID>')
def reboot(SerialID):
    try:
        SerialID = int(SerialID)
        s = struct.pack('<i',SerialID)
        ascii_PacketData = cmd_admin_reboot_reader + binascii.b2a_hex(s)
        binary_PacketData = binascii.a2b_hex(ascii_PacketData)
        SendBinDataToServer(binary_PacketData)
        return {"status":"0","message":"Success"}
    except ValueError:
        return {"status":"1","message":"SerialID Invalid"}


#@Sync Server Time To Specified Device
@app.route('/kqdevapi/synctime/<SerialID>')
def synctime(SerialID):
    try:
        SerialID = int(SerialID)
        s = struct.pack('<i',SerialID)
        ascii_PacketData = cmd_admin_sync_time + binascii.b2a_hex(s)
        binary_PacketData = binascii.a2b_hex(ascii_PacketData)
        SendBinDataToServer(binary_PacketData)
        return {"status":"0","message":"Success"}
    except ValueError:
        return {"status":"1","message":"SerialID Invalid"}


#@Reset System Parameters To Specified Device Of Software Version v1.0
@app.route('/kqdevapi/setnetpara/<SerialID>/<ServerIP>/<ServerPort>/<DeviceIP>/<NetMask>/<Gateway>/<NewSerialID>/<NewHBInt>/<NewCardInt>/<NewAPNum>')
def setnetpara(SerialID,ServerIP,ServerPort,DeviceIP,NetMask,Gateway,NewSerialID,NewHBInt,NewCardInt,NewAPNum):
    try:
        SerialID = int(SerialID)
        BinSerialID = struct.pack('<i',SerialID)
        ascii_SerialID = binascii.b2a_hex(BinSerialID)

        # Check New Server Port
        ServerPort = int(ServerPort)
        BinServerPort = struct.pack('<H',ServerPort)
        ascii_ServerPort = binascii.b2a_hex(BinServerPort)
        if ServerPort > 65535:
            return {"status":"1","message":"Server Port Need Less Than 65535"}

        # Check Device New Serial ID
        NewSerialID = int(NewSerialID)
        bin_NewSerialID = struct.pack('<i',NewSerialID)
        ascii_NewSerialID = binascii.b2a_hex(bin_NewSerialID)        

        # Check New Server IP 
        ascii_ServerIP = ConIPFormat(ServerIP)
        # Check Device New IP
        ascii_DeviceIP = ConIPFormat(DeviceIP)
        # Check Devcie New NetMask 
        ascii_NetMask = ConIPFormat(NetMask)
        # Check Device New Gateway
        ascii_Gateway = ConIPFormat(Gateway)

        # Check Device New Heartbeat Packet Time Interval
        NewHBInt = int(NewHBInt)
        BinHBInt = struct.pack('<B',NewHBInt)
        ascii_HBInt = binascii.b2a_hex(BinHBInt)
        if NewHBInt <= 0 or NewHBInt > 255:
            return {"status":"1","message":"Heartbeat Interval Value Invalid"}

        # Check Device New Card Induction Time Interval
        NewCardInt = int(NewCardInt)
        BinCardInt = struct.pack('<B',NewCardInt)
        ascii_CardInt = binascii.b2a_hex(BinCardInt)
        if NewCardInt <=0 or NewCardInt > 180:
            return {"status":"1","message":" Card Induction Time Interval Value Invalid"}
        
        # Check Device New Antenna Power 
        NewAPNum = int(NewAPNum)
        BinAPNum = struct.pack('<B',NewAPNum)
        ascii_APNum = binascii.b2a_hex(BinAPNum)
        if NewAPNum <= 0  or NewAPNum > 150:
            return {"status":"1","message":"Antenna Power Num Invalid"}

        if ascii_ServerIP == None or ascii_DeviceIP == None or ascii_NetMask == None or ascii_Gateway == None:
            return {"status":"1","message":" Net Parameters Invalid"}
        else:
            ascii_PacketData =  cmd_admin_set_net_para + ascii_SerialID + ascii_ServerIP + ascii_ServerPort + ascii_DeviceIP + ascii_NetMask + ascii_Gateway 
            ascii_PacketData = ascii_PacketData + ascii_NewSerialID + ascii_HBInt + ascii_CardInt + ascii_APNum
            binary_PacketData =  binascii.a2b_hex(ascii_PacketData)
            SendBinDataToServer(binary_PacketData)
            return {"status":"0","message":"Success"}
    except ValueError:
        return {"status":"1","message":"Parameters Invalid,Please Check Parameters"}


#@Reset System Parameters To Specified Device Of Software Version v2.0
# --------------------------------------
# 参数说明：
# ANNum : 选择读卡器主板上那几根天线。00000001 表示1号天线 ,00000010 表示2号天线 ,00000100 表示3号天线 ,00001000 表示4号天线.
#         默认是00000011  表示选用1，2号天线。
# ---------------------------------------
@app.route('/kqdevapi/setnetpara/<SerialID>/<ServerIP>/<ServerPort>/<DeviceIP>/<NetMask>/<Gateway>/<NewSerialID>/<NewHBInt>/<NewCardInt>/<NewAPNum>/<NewANNum>')
def setnetpara(SerialID,ServerIP,ServerPort,DeviceIP,NetMask,Gateway,NewSerialID,NewHBInt,NewCardInt,NewAPNum,NewANNum):
    try:
        SerialID = int(SerialID)
        BinSerialID = struct.pack('<i',SerialID)
        ascii_SerialID = binascii.b2a_hex(BinSerialID)

        # Check New Server Port
        ServerPort = int(ServerPort)
        BinServerPort = struct.pack('<H',ServerPort)
        ascii_ServerPort = binascii.b2a_hex(BinServerPort)
        if ServerPort > 65535:
            return {"status":"1","message":"Server Port Need Less Than 65535"}

        # Check Device New Serial ID
        NewSerialID = int(NewSerialID)
        bin_NewSerialID = struct.pack('<i',NewSerialID)
        ascii_NewSerialID = binascii.b2a_hex(bin_NewSerialID)        

        # Check New Server IP 
        ascii_ServerIP = ConIPFormat(ServerIP)
        # Check Device New IP
        ascii_DeviceIP = ConIPFormat(DeviceIP)
        # Check Devcie New NetMask 
        ascii_NetMask = ConIPFormat(NetMask)
        # Check Device New Gateway
        ascii_Gateway = ConIPFormat(Gateway)

        # Check Device New Heartbeat Packet Time Interval
        NewHBInt = int(NewHBInt)
        BinHBInt = struct.pack('<B',NewHBInt)
        ascii_HBInt = binascii.b2a_hex(BinHBInt)
        if NewHBInt <= 0 or NewHBInt > 255:
            return {"status":"1","message":"Heartbeat Interval Value Invalid"}

        # Check Device New Card Induction Time Interval
        NewCardInt = int(NewCardInt)
        BinCardInt = struct.pack('<B',NewCardInt)
        ascii_CardInt = binascii.b2a_hex(BinCardInt)
        if NewCardInt <=0 or NewCardInt > 180:
            return {"status":"1","message":" Card Induction Time Interval Value Invalid"}
        
        # Check Device New Antenna Power 
        NewAPNum = int(NewAPNum)
        BinAPNum = struct.pack('<B',NewAPNum)
        ascii_APNum = binascii.b2a_hex(BinAPNum)
        if NewAPNum <= 0  or NewAPNum > 150:
            return {"status":"1","message":"Antenna Power Num Invalid"}

        # Check Device New Antenna Number
        NewANNum = int(NewANNum)
        BinANNum = struct.pack('<B',NewANNum)
        ascii_ANNum = binascii.b2a_hex(BinANNum)
        if NewANNum <= 0  or NewANNum > 15:
            return {"status":"1","message":"Antenna Number Invalid"}        


        if ascii_ServerIP == None or ascii_DeviceIP == None or ascii_NetMask == None or ascii_Gateway == None:
            return {"status":"1","message":" Net Parameters Invalid"}
        else:
            ascii_PacketData =  cmd_admin_set_net_para + ascii_SerialID + ascii_ServerIP + ascii_ServerPort + ascii_DeviceIP + ascii_NetMask + ascii_Gateway 
            ascii_PacketData = ascii_PacketData + ascii_NewSerialID + ascii_HBInt + ascii_CardInt + ascii_APNum + ascii_ANNum
            binary_PacketData =  binascii.a2b_hex(ascii_PacketData)
            SendBinDataToServer(binary_PacketData)
            return {"status":"0","message":"Success"}
    except ValueError:
        return {"status":"1","message":"Parameters Invalid,Please Check Parameters"}


#@send command to device for get config parameter
@app.route('/kqdevapi/getconf/<SerialID>')
def getconf(SerialID):
    try:
        SerialID = int(SerialID)
        s = struct.pack('<i',SerialID)
        ascii_PacketData = cmd_admin_get_conf_para + binascii.b2a_hex(s)
        binary_PacketData = binascii.a2b_hex(ascii_PacketData)
        SendBinDataToServer(binary_PacketData)
        return {"status":"0","message":"Success"}
    except ValueError:
        return {"status":"1","message":"SerialID Invalid"}


#@Set Heartbeat Packet Interval To Specified Device
@app.route('/kqdevapi/sethbtime/<SerialID>/<HBInt>')
def sethbtime(SerialID,HBInt):
    try:
        SerialID = int(SerialID)
        BinSerialID = struct.pack('<i',SerialID)
        ascii_SerialID = binascii.b2a_hex(BinSerialID)
        HBInt = int(HBInt)
        BinHBInt = struct.pack('<B',HBInt)
        ascii_HBInt = binascii.b2a_hex(BinHBInt)
        if HBInt <= 0 or HBInt > 60:
            return {"status":"1","message":"Heartbeat Interval Value Invalid"}
        ascii_PacketData = cmd_admin_set_heartbeat_interval + ascii_SerialID + ascii_HBInt
        binary_PacketData =  binascii.a2b_hex(ascii_PacketData)
        SendBinDataToServer(binary_PacketData)
        return {"status":"0","message":"Success"}
    except ValueError:
        return {"status":"1","message":"SerialID OR Heartbeat Interval Value Invalid"}


#@Set Antenna Power To Specified Device
@app.route('/kqdevapi/setapower/<SerialID>/<APNum>')
def setapower(SerialID,APNum):
    try:    
        SerialID = int(SerialID)
        BinSerialID = struct.pack('<i',SerialID)
        ascii_SerialID = binascii.b2a_hex(BinSerialID)
        APNum = int(APNum)
        BinAPNum = struct.pack('<B',APNum)
        ascii_APNum = binascii.b2a_hex(BinAPNum)
        if APNum <= 0  or APNum > 150:
            return {"status":"1","message":"Antenna Power Num Invalid"}
        ascii_PacketData = cmd_admin_antenna_power + ascii_SerialID + ascii_APNum
        binary_PacketData =  binascii.a2b_hex(ascii_PacketData)
        SendBinDataToServer(binary_PacketData)
        return {"status":"0","message":"Success"}
    except ValueError:
        return {"status":"1","message":"SerialID OR Antenna Power Num Invalid"}


#@Set Reader SerialID To Specified Device
@app.route('/kqdevapi/setserialid/<OldSerialID>/<NewSerialID>')
def setserialid(OldSerialID,NewSerialID):
    try:
        OldSerialID = int(OldSerialID)
        NewSerialID = int(NewSerialID)
        bin_OldSerialID = struct.pack('<i',OldSerialID)
        ascii_OldSerialID = binascii.b2a_hex(bin_OldSerialID)
        bin_NewSerialID = struct.pack('<i',NewSerialID)
        ascii_NewSerialID = binascii.b2a_hex(bin_NewSerialID)        
        ascii_PacketData = cmd_admin_set_reader_serialid + ascii_OldSerialID + ascii_NewSerialID
        binary_PacketData =  binascii.a2b_hex(ascii_PacketData)
        SendBinDataToServer(binary_PacketData)
        return {"status":"0","message":"Success"}
    except ValueError:
        return {"status":"1","message":"SerialID Format Invalid"}


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
try:
    run(app,host="61.183.254.135",port=9008) 
except Exception,e:
    logger.error("Main Program Quit,Error is %s"%e)
    sys.exit()





    







