#!/usr/bin/env python
# -*- coding: utf-8 -*-

#----------------------------------------------
# @Date    : 2017-02-09 16:41:17
# @Author  : wye
# @Version : v1.0
# @Descr   : monitor for docker 
# ---------------------------------------------

import sys
import time
import json
import httplib
from datetime import datetime

#---------------------------
# cadvisor related variables
#---------------------------

CadvisorHost="172.29.150.112"
CadvisorPort=8081

# --------------------------
# docker related variables
# --------------------------

DockerHost="172.29.150.112"
DockerPort=2375


# -------------------------
# other
# -------------------------

DataSourceTag="CadvisorApi"  
#DataSourceTag="DockerApi"


def CallApiGetData(Host,Port,ReqUrlSuffix):
    """
    Call api interface for get docker and container information
    """
    httpClient = None
    try:
        httpClient = httplib.HTTPConnection(Host,Port,timeout=2)
        httpClient.request('GET',ReqUrlSuffix)
        response = httpClient.getresponse()
        if response.status == 200:
            resp_string = response.read()
            resp_format_data = json.loads(resp_string)
            return resp_format_data
        else:
            print("call api fail!,return code %s"%response.status)
    except Exception,e:
        print("call api error!,%s"%e)
    finally:
        if httpClient:
            httpClient.close()


class ExecFunByZabbixRequest(object):
    """
    Execute functions based on zabbix request 
    """

    def __init__(self,ParasList):

        self.DataSourceTag = DataSourceTag

        self.DockerHost = DockerHost
        self.DockerPort = DockerPort

        self.CadvisorHost = CadvisorHost
        self.CadvisorPort = CadvisorPort

        try:
            FunObj = getattr(self,ParasList[0])
        except AttributeError:
            print "Without this function of %s"%(ParasList[0])
        else:
            FunObj(ParasList[1:])

    # ---------------------
    # Part one
    # ---------------------

    def DockerContainersDiscovery(self,ParasList):
        """
        Return all running containers id in localhost
        """
        TmpDict = {}
        TmpList = []

        ReqUrlSuffix = '/v1.22/containers/json'
        RetDataList = CallApiGetData(self.DockerHost,self.DockerPort,ReqUrlSuffix)

        for cdict in RetDataList:
            TmpList.append({"{#CONTAINERID}":cdict['Id']})

        TmpDict["data"] = TmpList

        print json.dumps(TmpDict) 


    def DockerStatus(self,ParasList):
        """
        Return docker daemon global status value

        Monitor metrics:
        RunningContainerNum -> the number of containers running 
        ExitedContainerNum -> the number of containers has been stopped
        """

        MonStr = ParasList[0]
        if MonStr == "RunningContainerNum":
            ReqUrlSuffix = '/v1.22/containers/json?filters={"status":["running"]}'
            RetDataList = CallApiGetData(self.DockerHost,self.DockerPort,ReqUrlSuffix)
            print len(RetDataList)
        elif MonStr == "ExitedContainerNum":
            ReqUrlSuffix = '/v1.22/containers/json?filters={"status":["exited"]}'
            RetDataList = CallApiGetData(self.DockerHost,self.DockerPort,ReqUrlSuffix)
            print len(RetDataList)
        else:
            print("Unsupported monitoring metrics")


    def DockerContainerStatus(self,ParasList):
        """
        Return a single container status message

        Monitor metrics:
        LimitMemory -> the max memory that the container can use
        Memory -> the container consumes memory
        MemoryPercentUsage -> the container memory percent usage
        CpuTotalUsage -> the container total cpu percent usage
        NetIfInput -> the container network interface input rate
        NetIfOutput -> the container network interface output rate
        """

        Cid = ParasList[0]
        MonStr = ParasList[1]

        if MonStr == "LimitMemory":
            print self.GetLimitMemory(Cid)
        elif MonStr == "Memory":
            print self.GetMemory(Cid)
        elif MonStr == "MemoryPercentUsage":
            print self.GetMemoryPercentUsage(Cid)
        elif MonStr == "CpuTotalUsage":
            self.GetCpuTotalUsage(Cid)
        elif MonStr == "NetIfInput":
            self.GetNetIfInput(Cid)
        elif MonStr == "NetIfOutput":
            self.GetNetIfOutput(Cid)
        else:
            print("Unsupported monitoring metrics")

    
    # -------------------
    # Part two
    # -------------------

    def GetLimitMemory(self,Cid):
        """
        Get the container limit memory from docker or cadvisor api 
        based on data source tag in code 
        """
        if self.DataSourceTag == "DockerApi":
            ReqUrlSuffix = "/v1.22/containers/%s/stats?stream=false"%Cid
            RetDataDict = CallApiGetData(self.DockerHost,self.DockerPort,ReqUrlSuffix)
            LimitMemory = RetDataDict["memory_stats"]["limit"]
        elif self.DataSourceTag == "CadvisorApi":
            ReqUrlSuffix = "/v1.22/containers/%s/stats?stream=false"%Cid
            RetDataDict = CallApiGetData(self.DockerHost,self.DockerPort,ReqUrlSuffix)
            LimitMemory = RetDataDict["memory_stats"]["limit"]

        return LimitMemory

    def GetMemory(self,Cid):
        """
        Get the container used memory from docker or cadvisor api 
        based on data source tag in code 
        """
        if self.DataSourceTag == "DockerApi":
            ReqUrlSuffix = "/v1.22/containers/%s/stats?stream=false"%Cid
            RetDataDict = CallApiGetData(self.DockerHost,self.DockerPort,ReqUrlSuffix)
            Memory = RetDataDict["memory_stats"]["usage"]
        elif self.DataSourceTag == "CadvisorApi":
            ReqUrlSuffix = "/api/v2.0/stats/%s?type=docker&count=1"%Cid
            RetDataDict = CallApiGetData(self.CadvisorHost,self.CadvisorPort,ReqUrlSuffix)
            for value in RetDataDict.values():
                Memory = value[0]["memory"]["usage"]
        
        return Memory

    def GetMemoryPercentUsage(self,Cid):
        """
        Get the container Memory Percent Usage 
        """
        Memory = self.GetMemory(Cid)
        LimitMemory = self.GetLimitMemory(Cid)
        MemoryPercentUsage = "%.2f"%(float(Memory)/float(LimitMemory)*100)
        return MemoryPercentUsage

    def GetCpuTotalUsage(self,Cid):
        """
        Get the container cpu Total Usage from docker or cadvisor api 
        based on data source tag in code 
        """
        if self.DataSourceTag == "DockerApi":
            PreDataDict,CurDataDict = self.GetBaseDataFromDockerApi(Cid)
            IntervalNs = (self.TimeStrToTimestamp(CurDataDict["read"]) - self.TimeStrToTimestamp(PreDataDict["read"]))*1000000
            IntervalCpu = CurDataDict["cpu_stats"]["cpu_usage"]["total_usage"] - PreDataDict["cpu_stats"]["cpu_usage"]["total_usage"]
            CpuTotalUsage = "%.3f"%(float(IntervalCpu)/float(IntervalNs))
            print CpuTotalUsage
        elif self.DataSourceTag == "CadvisorApi":
            PreDataDict,CurDataDict = self.GetBaseDataFromCadvisorApi(Cid)
            IntervalNs = (self.TimeStrToTimestamp(CurDataDict["timestamp"]) - self.TimeStrToTimestamp(PreDataDict["timestamp"]))*1000000
            IntervalCpu = CurDataDict["cpu"]["usage"]["total"] - PreDataDict["cpu"]["usage"]["total"]
            CpuTotalUsage = "%.3f"%(float(IntervalCpu)/float(IntervalNs))
            print CpuTotalUsage
        else:
            print("No invaild api tag")

    def GetNetIfInput(self,Cid):
        """
        Get the container network input rate from docker or cadvisor api 
        based on data source tag in code 
        """
        if self.DataSourceTag == "DockerApi":
            PreDataDict,CurDataDict = self.GetBaseDataFromDockerApi(Cid)
            IntervalInSec = "%.3f"%(float((self.TimeStrToTimestamp(CurDataDict["read"]) - self.TimeStrToTimestamp(PreDataDict["read"])))/1000)
            IntervalRxBytes = CurDataDict["networks"]["eth0"]["rx_bytes"] - PreDataDict["networks"]["eth0"]["rx_bytes"]
            NetIfInput = IntervalRxBytes/float(IntervalInSec)
            print "%.3f"%NetIfInput
        elif self.DataSourceTag == "CadvisorApi":
            PreDataDict,CurDataDict = self.GetBaseDataFromCadvisorApi(Cid)
            IntervalInSec = "%.3f"%(float((self.TimeStrToTimestamp(CurDataDict["timestamp"]) - self.TimeStrToTimestamp(PreDataDict["timestamp"])))/1000)
            IntervalRxBytes = CurDataDict["network"]["interfaces"][0]["rx_bytes"] - PreDataDict["network"]["interfaces"][0]["rx_bytes"]
            NetIfInput = IntervalRxBytes/float(IntervalInSec)
            print "%.3f"%NetIfInput
        else:
            print("No invaild api tag")
    
    def GetNetIfOutput(self,Cid):
        """
        Get the container network output rate from docker or cadvisor api 
        based on data source tag in code 
        """
        if self.DataSourceTag == "DockerApi":
            PreDataDict,CurDataDict = self.GetBaseDataFromDockerApi(Cid)
            IntervalInSec = "%.3f"%(float((self.TimeStrToTimestamp(CurDataDict["read"]) - self.TimeStrToTimestamp(PreDataDict["read"])))/1000)
            IntervalTxBytes = CurDataDict["networks"]["eth0"]["tx_bytes"] - PreDataDict["networks"]["eth0"]["tx_bytes"]
            NetIfOutput = IntervalTxBytes/float(IntervalInSec)
            print "%.3f"%NetIfOutput
        elif self.DataSourceTag == "CadvisorApi":
            PreDataDict,CurDataDict = self.GetBaseDataFromCadvisorApi(Cid)
            IntervalInSec = "%.3f"%(float((self.TimeStrToTimestamp(CurDataDict["timestamp"]) - self.TimeStrToTimestamp(PreDataDict["timestamp"])))/1000)
            IntervalTxBytes = CurDataDict["network"]["interfaces"][0]["tx_bytes"] - PreDataDict["network"]["interfaces"][0]["tx_bytes"]
            NetIfOutput = IntervalTxBytes/float(IntervalInSec)
            print "%.3f"%NetIfOutput
        else:
            print("No invaild api tag")
    

    # -------------------
    # Part three
    # -------------------
    
    def GetBaseDataFromDockerApi(self,Cid):
        """
        Get metric base data from docker api
        """
        ReqUrlSuffix = "/v1.22/containers/%s/stats?stream=false"%Cid
        PreDataDict = CallApiGetData(self.DockerHost,self.DockerPort,ReqUrlSuffix)
        #time.sleep(0.001)
        CurDataDict = CallApiGetData(self.DockerHost,self.DockerPort,ReqUrlSuffix)
        return PreDataDict,CurDataDict
    
    def GetBaseDataFromCadvisorApi(self,Cid):
        """
        Get metric base data from cadvisor api
        """
        ReqUrlSuffix = "/api/v2.0/stats/%s?type=docker&count=2"%Cid
        RawDataDict = CallApiGetData(self.CadvisorHost,self.CadvisorPort,ReqUrlSuffix)
        for value in RawDataDict.values():
            PreDataDict = value[0]
            CurDataDict = value[1]
        return PreDataDict,CurDataDict

    def TimeStrToTimestamp(self,TimeStr):
        """
        Time string transform to timestamp (ms)
        """
        Ymd = TimeStr[0:10]
        HMS = TimeStr[11:26]
        NewTimeStr = "%s %s"%(Ymd,HMS)

        datetime_obj=datetime.strptime(NewTimeStr,'%Y-%m-%d %H:%M:%S.%f')
        local_timestamp = long(time.mktime(datetime_obj.timetuple()) * 1000.0 + datetime_obj.microsecond / 1000.0)

        return local_timestamp

if __name__ == "__main__":
    """
    For debug
    """
    ExecFunByZabbixRequest(sys.argv[1:])




