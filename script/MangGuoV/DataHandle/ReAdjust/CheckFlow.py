#!/usr/bin/env python
#-*- coding: utf-8 -*-

import time
import json
import datetime
import redis
import MySQLdb
import Queue
import threading
#from pymongo import MongoClient
from UserInfo import UidInfo
from UserInfo import TypeInfo
import smtplib
from email.mime.text import MIMEText 
#from PubMod import HandleConfig
#from PubMod import getLog

Mail_list = {"server":"59.175.153.69",
             "fromAddr": "tech@skygrande.com",
             "user":"tech",
             "passwd":""}
            
def SendMail(Mail_list,to,subject,text):
    msg = MIMEText(text,_charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = Mail_list["fromAddr"]
    msg["To"] = to
    try:
        send_smtp = smtplib.SMTP()
        send_smtp.connect(Mail_list["server"])
        send_smtp.sendmail(Mail_list["fromAddr"],to,msg.as_string())
        send_smtp.close()
        return True
    except Exception,e:
        print e
        pass

def is_leap_year(year):
    if (year%4 == 0 and year%100 != 0) or year%400 == 0:
        return True
    else:
        return False
    
def get_days_list(date,num):
    month_list = {"1":31,"3":31,"4":30,"5":31,"6":30,"7":31,"8":31,"9":30,"10":31,"11":30,"0":31}
    date_list = str(date).split("-")
    year = date_list[0]
    month = date_list[1]
    day = date_list[2] 
    year_num = num/12
    month_days = {}
    for i in range(num):
        month_num = int(month) + i
        if (month_num%12) !=2:
            month_days[str(month_num)] = month_list[str(month_num%12)]
        else:
            month_days[str(month_num)] = 28
    leap_year = []
    for i in range(year_num+2):
        if is_leap_year(int(year)+i):
            leap_year.append(29)
        else:
            leap_year.append(28)

    days_list = []
    sum = 0
    for i in month_days.iterkeys():
        if int(i)%12 == 2 :
            feb_days = int(i)/12
            month_days[i]= leap_year[feb_days]
            
    for i in month_days.iterkeys():
        sum += month_days[i]
        days_list.append(sum)

    new_days_list = days_list[:-1]
    #new_days_list.append(0)
    begin_day_list = []
    
    for i in new_days_list:
        timeObj = time.strptime(date,'%Y-%m-%d')
        dateObj = datetime.datetime(*timeObj[:3])
        new_begin_day = (dateObj+datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        begin_day_list.append(new_begin_day)
   
    
    return begin_day_list


def fall_type(total_flow,month_flow,typeflow):
    new_begindate = datetime.datetime.now().strftime("%Y-%m-%d")
    new_enddate = "0000-00-00"
    new_month_flow = typeflow
    new_month_count = 0
    now_month_used = total_flow - month_flow 
    if now_month_used >= 0:
        now_month_extr = now_month_used - typeflow
        if now_month_extr > 0:
            new_month_used_flow = typeflow
            new_month_advance_flow = now_month_extr
            is_flow_alarm = 1
            is_write_redis = 0
            
        elif now_month_extr < -typeflow*0.1:
            new_month_used_flow = now_month_used
            new_month_advance_flow = 0
            is_flow_alarm = 0
            is_write_redis = 1
             
        else:
            new_month_used_flow = now_month_used
            new_month_advance_flow = 0
            is_flow_alarm = 1
            is_write_redis = 1
            
    else:
        new_month_used_flow = 0
        new_month_advance_flow = 0
        is_flow_alarm = 0
        is_write_redis = 1
    return [new_begindate,new_enddate,new_month_count,new_month_flow,new_month_used_flow,new_month_advance_flow,is_flow_alarm,is_write_redis]


def CheckFlow(UidObj,redisconn,Mail_list):
    uid = UidObj.Uid
    mysqlconn = UidObj.mysqlconn
    cursor = mysqlconn.cursor()
    flow_info = UidObj.get_flow_info(uid)
    daily_flow = UidObj.get_daily_flow(uid)
    daily_flow = daily_flow/1024
    #daily_flow = 120
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    #today = "2013-06-24"
    enddate = str(flow_info[1])
    begindate = str(flow_info[0])
    month_count = flow_info[2]
    
    month_flow = flow_info[3]
    if flow_info[4] == None:
        month_used_flow = 0
    else:
        month_used_flow = flow_info[4]
    if flow_info[5] == None:
        month_advance_flow = 0
    else:
        month_advance_flow = flow_info[5]
    is_flow_alarm = flow_info[6]
    typeid = flow_info[7]
    if flow_info[8] == None:
        user_email = None
    else:
        user_email = flow_info[8]
        #user_email = "rli@cloudiya.com"
    begindate_list = get_days_list(begindate,month_count)
    if month_count == 0:
        last_one_month = "0000-00-00"
    else:
        last_one_month = begindate_list[-1:]
    subject2 = u"流量报警通知！"
    text2 =  u'''尊敬的天空视频网用户：

                     由于您本月使用的流量已经超过了购买的套餐月流量上限的90%，未防止你的视频播放中断，请尽快充值。

                     温馨提示：为了更好的提供我们的视频服务，对于所有的付费套餐用户，如果您未能及时充值，我们将
                               从您下个月的流量中借用10%来继续本月的流量使用。

                     祝您使用愉快，如果您有什么建议或其他反馈请联系我们客服。邮箱：support@skygrande.com
            '''
    subject3 = u"流量超支通知！！！"
    text3 = u'''尊敬的用户：
    
                     由于你购买的套餐流量已经超过了月流量，你的视频已经中断，请充值。
                     祝您使用愉快，如果您有什么建议或其他反馈请联系我们客服。邮箱：tech@skygrande.com
            '''
    total_used_flow = month_used_flow + month_advance_flow + daily_flow
    typeObj = TypeInfo(mysqlconn,2)
    if today == enddate:
        print "in the endtate mothed"
        ext_typeinfo = typeObj.get_ext_typeinfo(uid)
        if ext_typeinfo == []:
            "免费用户降级"
            data = fall_type(total_used_flow,month_flow,typeObj.flow)
            sqlOne = "update uflow set startdate=%s,enddate=%s,month_count=%s,month_flow=%s,month_used_flow=%s,month_advance_flow=%s,is_flow_alarm=%s where uid = %s"
            param = (data[0],data[1],data[2],data[3],data[4],data[5],data[6],uid)
            cursor.execute(sqlOne,param)
            mysqlconn.commit()
            redisconn.set("%s_flow"%uid,data[7])
            #同时更新uinfo中的套餐类型
            sqlTwo = "update uinfo set tid = 2 where uid = %s"
            cursor.execute(sqlTwo,uid)
            mysqlconn.commit()
            subject = u"套餐降级通知！"
            text = u'''尊敬的天空视频网用户：

                     由于你购买的套餐或者充值流量已经到期，所以我们自动将您降级为免费用户，免费用户将有2GB/月的流量使用
                        和1GB的存储空间。如果您现在所有的视频文件所占用的存储空间超过1GB，我们将在7天后删除您的视频文件
                        到占用存储空间不超过1GB为止。

                     祝您使用愉快，如果您有什么建议或其他反馈请联系我们客服。
 
                     邮箱：support@skygrande.com.
                '''
        
            SendMail(Mail_list,user_email,subject,text)
        else:
            old_starttime = str(ext_typeinfo[0])
            ext_enddate = str(ext_typeinfo[1])
            o_mount_flow = ext_typeinfo[2]
            is_ext = ext_typeinfo[3]
            total_mouth = ext_typeinfo[4]
            if is_ext == 1 :
                #套餐不续费,降级
                data = fall_type(total_used_flow,month_flow,typeObj.flow)
                sqlOne = "update uflow set startdate=%s,enddate=%s,month_count=%s,month_flow=%s,month_used_flow=%s,month_advance_flow=%s,is_flow_alarm=%s where uid = %s"
                param = (data[0],data[1],data[2],data[3],data[4],data[5],data[6],uid)
                cursor.execute(sqlOne,param)
                mysqlconn.commit()
                redisconn.set("%s_flow"%uid,data[7])
                #同时更新uinfo中的套餐类型
                sqlTwo = "update uinfo set tid = 2 where uid = %s"
                cursor.execute(sqlTwo,uid)
                mysqlconn.commit()
                subject = u"套餐降级通知！"
                text = u'''尊敬的天空视频网用户：

                           由于你购买的套餐或者充值流量已经到期，所以我们自动将您降级为免费用户，免费用户将有2GB/月的流量使用
                        和1GB的存储空间。如果您现在所有的视频文件所占用的存储空间超过1GB，我们将在7天后删除您的视频文件
                        到占用存储空间不超过1GB为止。

                         祝您使用愉快，如果您有什么建议或其他反馈请联系我们客服。
 
                         邮箱：support@skygrande.com.
                '''
        
                SendMail(Mail_list,user_email,subject,text)

            else:
                #套餐续费
                old_starttime_list = old_starttime.split("-")
                old_endtime_list = enddate.split('-')
                old_starttime_list[0] = str(old_endtime_list[0])
                new_starttime = '-'.join(old_starttime_list)
                new_enddate = ext_enddate
                new_month_count = total_mouth - month_count
                 
                sqlNine = "update uflow set startdate=%s,enddate=%s,month_count=%s,month_flow=%s,month_used_flow=%s,month_advance_flow=%s,is_flow_alarm=%s where uid =%s"
                now_month_used = total_used_flow - month_flow
                if now_month_used >= 0:
                    now_month_extr = now_month_used  - o_mount_flow
                    if now_month_extr > o_mount_flow*0.1:
                        new_month_used_flow = o_mount_flow
                        new_month_advance_flow = now_month_extr
                        is_flow_alarm = 1
                        is_write_redis = 0 
                        SendMail(Mail_list,user_email,subject3,text3)               
                    elif 0< now_month_extr <= o_mount_flow*0.1:
                        new_month_used_flow = o_mount_flow
                        new_month_advance_flow = now_month_extr
                        is_flow_alarm = 1
                        is_write_redis = 1 
                        SendMail(Mail_list,user_email,subject2,text2)               
                    elif -o_mount_flow*0.1 < now_month_extr <=0 :
                        new_month_used_flow = now_month_used
                        new_month_advance_flow = 0
                        is_flow_alarm = 1
                        is_write_redis = 1
                        SendMail(Mail_list,user_email,subject2,text2)  
                    else:
                        new_month_used_flow = now_month_used
                        new_month_advance_flow = 0
                        is_flow_alarm = 0
                        is_write_redis = 1                
                else: 
                    new_month_used_flow = 0
                    new_month_advance_flow = 0
                    is_flow_alarm = 0
                    is_write_redis = 1
                    
                print new_month_used_flow,new_month_advance_flow,is_flow_alarm,is_write_redis
                param = (new_starttime,new_enddate,new_month_count,o_mount_flow,new_month_used_flow,new_month_advance_flow,is_flow_alarm,uid)
                cursor.execute(sqlNine,param)
                mysqlconn.commit()  
                redisconn.set("%s_flow"%uid,is_write_redis)                
                #跟新ucurrntetc表，开启续费开关
                sqlTen = 'update ucurrenttc set xufei_status=1 where uid = %s' 
                param = (uid)
                cursor.execute(sqlTen,param)
                mysqlconn.commit()
                
    elif str(today) in begindate_list:
        "月初"
        print "in the month begging methed"
        if typeid == 2 and month_count == 0:
            "免费模式中的月初初始化，送2G流量"
            #当日使用流量+月已经使用流量+额外使用流量的值-2G 获得本月初始化后可以使用的流量
            if month_advance_flow >0:
                pass
            else:
                
                sqlThree = "update uflow set month_used_flow=%s,month_advance_flow=%s,is_flow_alarm=%s where uid = %s "
                now_month_used = total_used_flow - month_flow 
                now_month_extr = now_month_used - typeObj.flow 
                if now_month_used >= 0:
                    if now_month_extr >= 0:
                        new_month_used_flow = typeObj.flow
                        new_month_advance_flow = now_month_extr
                        is_flow_alarm = 1
                        is_write_redis = 0
                        SendMail(Mail_list,user_email,subject3,text3)
                    elif now_month_extr < -typeObj.flow*0.1:
                        new_month_used_flow = now_month_used
                        new_month_advance_flow = 0
                        is_flow_alarm = 0
                        is_write_redis = 1
                    
                    else:
                        new_month_used_flow = now_month_used
                        new_month_advance_flow = 0
                        is_flow_alarm = 1
                        is_write_redis = 1
                        SendMail(Mail_list,user_email,subject2,text2)
                else:
                    new_month_used_flow = 0
                    new_month_advance_flow = 0
                    is_flow_alarm = 0
                    is_write_redis =1                
            
                param = (new_month_used_flow,new_month_advance_flow,is_flow_alarm,uid)
                cursor.execute(sqlThree,param)
                mysqlconn.commit() 
                redisconn.set("%s_flow"%uid,is_write_redis)
                
        elif typeid == 2 and month_count != 0:
            now_month_used = total_used_flow - month_flow 
            sqlFour = "update uflow set month_flow=%s,month_used_flow=%s,month_advance_flow=%s,is_flow_alarm=%s where uid =%s"           
            if now_month_used > 0:
                #降级
                data = fall_type(total_used_flow,month_flow,typeObj.flow)
                sqlOne = "update uflow set startdate=%s,enddate=%s,month_count=%s,month_flow=%s,month_used_flow=%s,month_advance_flow=%s,is_flow_alarm=%s where uid = %s"
                param = (data[0],data[1],data[2],data[3],data[4],data[5],data[6],uid)
                cursor.execute(sqlOne,param)
                mysqlconn.commit()
                redisconn.set("%s_flow"%uid,data[7])
                #同时更新uinfo中的套餐类型
                sqlTwo = "update uinfo set tid = 2 where uid = %s"
                cursor.execute(sqlTwo,uid)
                mysqlconn.commit()  
                subject = u"套餐降级通知！！！"
                text = u'''尊敬的天空视频网用户：

                     由于你购买的套餐或者充值流量已经到期，所以我们自动将您降级为免费用户，免费用户将有2GB/月的流量使用
                        和1GB的存储空间。如果您现在所有的视频文件所占用的存储空间超过1GB，我们将在7天后删除您的视频文件
                        到占用存储空间不超过1GB为止。

                     祝您使用愉快，如果您有什么建议或其他反馈请联系我们客服。

                     邮箱：support@skygrande.com.
                          '''
                SendMail(Mail_list,user_email,subject,text)                                             
            elif now_month_used < -month_flow*0.1:
                new_month_flow = month_flow 
                new_month_used_flow = total_used_flow
                new_month_advance_flow = 0
                is_flow_alarm = 0
                is_write_redis = 1
                param = (new_month_flow,new_month_used_flow,new_month_advance_flow,is_flow_alarm,uid)
                cursor.execute(sqlFour,param)
                mysqlconn.commit()                
                redisconn.set("%s_flow"%uid,is_write_redis)                
            else:
                new_month_flow = month_flow 
                new_month_used_flow = total_used_flow
                new_month_advance_flow = 0
                is_flow_alarm = 1
                is_write_redis = 1 
                param = (new_month_flow,new_month_used_flow,new_month_advance_flow,is_flow_alarm,uid)
                cursor.execute(sqlFour,param)
                mysqlconn.commit()                
                redisconn.set("%s_flow"%uid,is_write_redis)
                SendMail(Mail_list,user_email,subject2,text2)
                
                
        else:
            #套餐用户月初初始化
            sqlFive = "update uflow set month_used_flow=%s,month_advance_flow=%s,is_flow_alarm=%s where uid =%s"
            now_month_used = total_used_flow - month_flow
            if now_month_used >= 0:
                now_month_extr = now_month_used  - month_flow
                if now_month_extr > month_flow*0.1:
                    new_month_used_flow = month_flow
                    new_month_advance_flow = now_month_extr
                    is_flow_alarm = 1
                    is_write_redis = 0 
                    SendMail(Mail_list,user_email,subject3,text3)               
                elif 0< now_month_extr <= month_flow*0.1:
                    new_month_used_flow = month_flow
                    new_month_advance_flow = now_month_extr
                    is_flow_alarm = 1
                    is_write_redis = 1 
                    SendMail(Mail_list,user_email,subject2,text2)               
                elif -month_flow*0.1 < now_month_extr <=0 :
                    new_month_used_flow = now_month_used
                    new_month_advance_flow = 0
                    is_flow_alarm = 1
                    is_write_redis = 1
                    SendMail(Mail_list,user_email,subject2,text2)  
                else:
                    new_month_used_flow = now_month_used
                    new_month_advance_flow = 0
                    is_flow_alarm = 0
                    is_write_redis = 1                
            else: 
                new_month_used_flow = 0
                new_month_advance_flow = 0
                is_flow_alarm = 0
                is_write_redis = 1
            print new_month_used_flow,new_month_advance_flow,is_flow_alarm,is_write_redis
            param = (new_month_used_flow,new_month_advance_flow,is_flow_alarm,uid)
            cursor.execute(sqlFive,param)
            mysqlconn.commit()  
            redisconn.set("%s_flow"%uid,is_write_redis)
            
    else:
        "月中"
        print "in the month between beging and end method"
        now_month_used = total_used_flow - month_flow
        if typeid == 2 and month_count != 0:
            if now_month_used >= 0:
                #降级
                data = fall_type(total_used_flow,month_flow,typeObj.flow)
                sqlOne = "update uflow set startdate=%s,enddate=%s,month_count=%s,month_flow=%s,month_used_flow=%s,month_advance_flow=%s,is_flow_alarm=%s where uid = %s"
                param = (data[0],data[1],data[2],data[3],data[4],data[5],data[6],uid)
                cursor.execute(sqlOne,param)
                mysqlconn.commit()
                redisconn.set("%s_flow"%uid,data[7])
                #同时更新uinfo中的套餐类型
                sqlTwo = "update uinfo set tid = 2 where uid = %s"
                cursor.execute(sqlTwo,uid)
                mysqlconn.commit()  
                subject = u"套餐降级通知！！！"
                text = u'''尊敬的天空视频网用户：

                     由于你购买的套餐或者充值流量已经到期，所以我们自动将您降级为免费用户，免费用户将有2GB/月的流量使用
                        和1GB的存储空间。如果您现在所有的视频文件所占用的存储空间超过1GB，我们将在7天后删除您的视频文件
                        到占用存储空间不超过1GB为止。

                     祝您使用愉快，如果您有什么建议或其他反馈请联系我们客服。

                     邮箱：support@skygrande.com.

                    '''
                SendMail(Mail_list,user_email,subject,text)                                         
            else:
                sqlSix = "update uflow set month_used_flow=%s,month_advance_flow=%s,is_flow_alarm=%s where uid =%s"
                if total_used_flow > month_flow*0.9 :
                    new_month_used_flow = total_used_flow
                    new_month_advance_flow = 0
                    is_flow_alarm = 1
                    is_write_redis = 1
                    SendMail(Mail_list,user_email,subject2,text2)
                else:
                    new_month_used_flow = total_used_flow
                    new_month_advance_flow = 0
                    is_flow_alarm = 0
                    is_write_redis = 1
                param = (new_month_used_flow,new_month_advance_flow,is_flow_alarm,uid)
                cursor.execute(sqlSix,param)
                mysqlconn.commit()
                redisconn.set("%s_flow"%uid,is_write_redis)
                                
                
                
        elif month_count == 0:
            sqlSeven = "update uflow set month_used_flow=%s,month_advance_flow=%s,is_flow_alarm=%s where uid =%s"
            if now_month_used >= 0:
                new_month_used_flow = month_flow
                new_month_advance_flow = now_month_used
                is_flow_alarm = 1
                is_write_redis = 0
                SendMail(Mail_list,user_email,subject3,text3)
            elif now_month_used < -month_flow*0.1:
                new_month_used_flow = total_used_flow
                new_month_advance_flow = 0
                is_flow_alarm = 0
                is_write_redis = 1
            else:
                new_month_used_flow = total_used_flow
                new_month_advance_flow = 0
                is_flow_alarm = 1
                is_write_redis = 1  
                SendMail(Mail_list,user_email,subject2,text2)
            param = (new_month_used_flow,new_month_advance_flow,is_flow_alarm,uid)
            cursor.execute(sqlSeven,param)
            mysqlconn.commit()
            redisconn.set("%s_flow"%uid,is_write_redis)            
        else:
            sqlEight = "update uflow set month_used_flow=%s,month_advance_flow=%s,is_flow_alarm=%s where uid =%s"
            if now_month_used > month_flow*0.1:
                new_month_used_flow = month_flow
                new_month_advance_flow = now_month_used
                is_flow_alarm = 1
                is_write_redis = 0
                SendMail(Mail_list,user_email,subject3,text3)               
            elif 0 < now_month_used <= month_flow*0.1:
                new_month_used_flow = month_flow
                new_month_advance_flow = now_month_used
                is_flow_alarm = 1
                is_write_redis = 1
                SendMail(Mail_list,user_email,subject2,text2)
            elif -month_flow*0.1 < now_month_used <=0:
                new_month_used_flow = total_used_flow
                new_month_advance_flow = 0
                is_flow_alarm = 1
                is_write_redis = 1
                SendMail(Mail_list,user_email,subject2,text2)
            else:
                new_month_used_flow = total_used_flow
                new_month_advance_flow = 0
                is_flow_alarm = 0
                is_write_redis = 1               
            param = (new_month_used_flow,new_month_advance_flow,is_flow_alarm,uid)
            cursor.execute(sqlEight,param)
            mysqlconn.commit()
            redisconn.set("%s_flow"%uid,is_write_redis)   


class ChechFlowHandle(threading.Thread):
    def __init__(self,datadate,queue,mongoconn,redata,Config,logger):
        self.queue = queue
        self.redata = redata
        self.date = datadate
            
        self.mongoconn = mongoconn
        self.mysqlIP = Config.MysqldbIp        
        self.mysqlPort = Config.MysqldbPort
        self.mysqlUser = Config.MysqlUser
        self.mysqlPassword = Config.MysqlPassword
        self.mysqlDbname = Config.MysqlDbname
        self.Config = Config    
            
        self.logger = logger    
            
        try:
            self.mysql_conn = MySQLdb.connect(host=self.mysqlIP,user=self.mysqlUser,passwd=self.mysqlPassword,port=self.mysqlPort,db=self.mysqlDbname,charset="utf8")
            self.cursor = self.mysql_conn.cursor()

        except Exception,e:
            print "can't connecte the mysql database."
    
        threading.Thread.__init__(self)
    
    def run(self):
        while True:
                    
            uid = self.queue.get()
                    
            userObj = UidInfo(self.mysql_conn,self.mongoconn,uid)
            
            CheckFlow(userObj,self.redata,Mail_list)
            
            self.queue.task_done()
                     
def main():
    Config = HandleConfig()
    redispool = redis.ConnectionPool(host=Config.RedisIp,port=6379,db=0)
    redata = redis.Redis(connection_pool=redispool)    
    mongoconn = MongoClient(Config.MongodbIp,27017)
    mysql_conn = MySQLdb.connect(host=Config.MysqldbIp,user=Config.MysqlUser,port=Config.MysqldbPort,passwd=Config.MysqlPassword,db=Config.MysqlDbname,charset="utf8")

    logger = getLog("Step6",logfile=Config.LogFile,loglevel=Config.LogLevel)
    logger.info("Step6 Handle Start")
    
    set_alluser = redata.smembers("user_info")
    if redata.exists("CheckFlow_User"):
        checked_user = redata.smembers("CheckFlow_User")
        set_user = set_alluser - checked_user
        list_user = list(set_user)
    else:
        list_user = list(set_alluser)
        
    for i in list_user:
        userObj = UidInfo(mysql_conn,mongoconn,i)
        CheckFlow(userObj,redata,Mail_list)   
        redata.sadd("CheckFlow_User",i)
    
    
    if len(redata.smembers("CheckFlow_User")) == len(set_alluser):
        logger.info("Step6 Handle End")
        redata.delete("CheckFlow_User")
    else:
        logger.error("Step6 Handel error,please run it again!!!!")
    
if __name__ == "__main__":
    main()
    #Config = HandleConfig()
    #redispool = redis.ConnectionPool(host=Config.RedisIp,port=6379,db=0)
    #redata = redis.Redis(connection_pool=redispool)    
    #mongoconn = MongoClient(Config.MongodbIp,27017)
    #mysql_conn = MySQLdb.connect(host=Config.MysqldbIp,user=Config.MysqlUser,port=Config.MysqldbPort,passwd=Config.MysqlPassword,db=Config.MysqlDbname,charset="utf8")

    #logger = getLog("Step5",logfile=Config.LogFile,loglevel=Config.LogLevel)
    #logger.info("Step5 Handle Start")
    
    #list_user = list(redata.smembers("user_info"))
    #for i in list_user:
    #    userObj = UidInfo(mysql_conn,mongoconn,i)
    #    CheckFlow(userObj,redata,Mail_list)
    #list_user = ["l123"]
    #logger = getLog("Step5",logfile=Config.LogFile,loglevel=Config.LogLevel)
    #logger.info("Step5 Handle Start")
        
    #datadate = Config.date    
    #queue = Queue.Queue(0)
        
    #for i in range(Config.workers):
    #    worker_obj = ChechFlowHandle(datadate,queue,mongoconn,redata,Config,logger)
    #    worker_obj.setDaemon(True)
    #    worker_obj.start()
        
    #for item in list_user:
    #    print item
    #    queue.put(item)
        
    #queue.join()
    #time.sleep(10)
