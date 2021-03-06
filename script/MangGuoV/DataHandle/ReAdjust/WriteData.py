#!/usr/bin/env python
# -*- encoding:utf-8 -*-

"""
Created on Jan 9, 2013

@author: wye

Copyright @ 2012 - 2013  Cloudiya Tech . Inc 

"""

# --/
# 
#      WriteData.py是整个批处理的第五步 
#      
#      处理方式：
#         依据redis中存在的"T_engagesum_$uid_$date"keys,遍历有数据变动的用户,视频,用户类别.将数据写往mysql,mongodb,redis.
#         处理完成一个"T_engagesum_$uid_$date"就删除一个.
#         如在该步出现异常终止,重新执行该步,直至redis中所有"T_engagesum_$uid_$date"类key执行完成后,再进入下一步.
#
#      依赖数据：
#         T_engagesum_$uid_$date
#
# --/

import sys
import redis
import Queue
import time
from pymongo import MongoClient
from PubMod import getLog
from PubMod import HandleConfig
from PubMod import delTmpData
from HandleAction import HandleUserinfo
from HandleAction import handleEndList
from HandleAction import handleTVIDSET
from HandleAction import handleTUIDSET
from HandleAction import writeData


# --/
#     基础数据是否存在于redis
# --/

try:
    Config = HandleConfig()

    logger = getLog("Step5",logfile=Config.LogFile,loglevel=Config.LogLevel)
    
    logger.info("Step5 Handle Start")
    
    datadate = Config.date
    
    mongoconn = MongoClient(Config.MongodbIp,27017)
    
    redispool = redis.ConnectionPool(host=Config.RedisIp,port=6379,db=0)
    redata = redis.Redis(connection_pool=redispool)
    redpipe = redata.pipeline() 
        
    queue = Queue.Queue(0)
    
    for i in range(Config.workers):
        worker_obj = writeData(datadate,queue,mongoconn,redata,Config,logger)
        worker_obj.setDaemon(True)
        worker_obj.start()
    
    keylist = redata.keys("T_engagesum_*_%s"%(datadate))
    
    if len(keylist) > 0:   
        for item in keylist:
            queue.put(item)
    else:
        logger.error("Does not satisfy the data processing requirements")
        sys.exit(Config.EX_CODE_5)
    
    queue.join()
    
    #delTmpData(redata)

    logger.info("Step5 Handle Complete")

except Exception,e:
    logger.error(e)
    sys.exit(Config.EX_CODE_5)
