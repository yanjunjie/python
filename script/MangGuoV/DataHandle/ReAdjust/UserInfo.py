#!/usr/bin/env python
#-*- coding: utf-8 -*-
# 这个脚本记录了用户的uid信息，vid的信息，还有kid的信息
# 会定时更新用户的数据统计

import MySQLdb
from pymongo import Connection
from pymongo import ReplicaSetConnection
#from dataHandle import mail_info
import redis
import time
import json
import ujson
import datetime

class UidInfo(object):
    '''
        class UidInfo
        function     get_uid_vidsum      get how much did this  uid have videos .return sum and the list about those videos
                     get_uid_kid         get the kid about uid .return kid list
                     usum_exists         if table  sta_usum in video database
                     ugeo_exists         if table  sta_ugeo in video database
                     get_uid_info        get uid info from mongodb
                     update_usum         updata table sta_usum about video database
                     update_ugeo         updata table sta_ugeo about video database 
    '''
    def __init__(self,mysqlconn,mongodbconn,uid):
        
       
        self.Uid = uid
        
        self.mysqlconn = mysqlconn
        
        self.mongodbconn = mongodbconn
        
        self.cursor = self.mysqlconn.cursor()   
        
        #self.setup_userinfo()
        #self.date = datetime.datetime.now().strftime("%Y%m%d")    
        self.date = (datetime.datetime.now()-datetime.timedelta(days=1)).strftime("%Y%m%d")
        
    '''    
    def setup_userinfo(self):
       # get the user more information from umore table in video database.
        pass
        try:
            sql = "
                select  user_type,flow_permonth,flow_usedmonth,permonth_begintime,is_warnning,flow_total,flow_usedtotal,pay_begintime,pay_endtime,recharge_begintime,recharge_endtime from umort where uid = %s
            "
            param = (uid)
            self.cursor.execute(sql, param)
            row = self.cursor.fetchone()
            if row == None or len(row) == 0:
                self.user_type = None
                self.flow_permonth = None
                self.flow_usedmonth = None
                self.permonth_begintime = None
                self.is_warnning = False
                self.flow_total = None
                self.flow_usedtotal = None
                self.pay_begintime = None
                self.pay_endtime = None
                self.recharge_begintime = None
                self.recharge_endtime = None 
            else:
                self.user_type = row[0]
                self.flow_permonth = row[1]
                self.flow_usedmonth = row[2]
                self.permonth_begintime = row[3]
                self.is_warnning = row[4]
                self.flow_total = row[5]
                self.flow_usedtotal = row[6]
                self.pay_begintime = row[7]
                self.pay_endtime = row[8]
                self.recharge_begintime = row[9]
                self.recharge_endtime = row[10]
        except Exception,e:
            print "Sorry,can not connect to mysql,error:%s" % e
            '''
    def get_flow_info(self,uid):
        sql = 'select  startdate,enddate,month_count,month_flow,month_used_flow,month_advance_flow,is_flow_alarm from uflow where uid = %s'
        param = (uid)
        self.cursor.execute(sql, param)
        row = self.cursor.fetchone()
        flow_list_info = []
        if row == None or len(row) == 0:
            flow_list_info = []
        else:
            for i in row:
                flow_list_info.append(i)
            
            
        sql2 = 'select a.tid from uinfo as a left join uflow as b  on a.uid=b.uid where a.uid = %s'
        param = (uid)
        self.cursor.execute(sql2, param)
        row = self.cursor.fetchone()        
        if row == None or len(row) == 0: 
            flow_list_info.append("")
        else:
            flow_list_info.append(row[0])
            
        sql3 = "select email from uinfo where uid = %s"
        param = (uid)
        self.cursor.execute(sql3, param)
        row = self.cursor.fetchone()        
        if row == None or len(row) == 0: 
            flow_list_info.append("")
        else:
            flow_list_info.append(row[0])        
        return flow_list_info        
               

    def get_daily_flow(self,uid):
        uid_daily_t =  self.mongodbconn["video"]["%s_daily"%(uid)]
                            
        uid_daily_info = uid_daily_t.find_one({"_id":self.date}) 
                
        if uid_daily_info != None:
            flow = uid_daily_info["Traffic"]  
            return flow   
        else:
            return 0

    def get_uid_vidsum(self,uid):
        
        vid_list = []
        
        sql = '''
              select b.vid from uinfo as a left join vinfo as b on a.uname = b.uname where a.uid = %s   
            '''
            
        param = (uid)
                                                    
        n = self.cursor.execute(sql,param) 
        
        raws = self.cursor.fetchall()
        
        uidvideonums = n   
        
        if n ==0 or n == None:
            return int(uidvideonums),[]
        else:
            for i in raws:
                vid_list.append(i[0])
            return int(uidvideonums),vid_list        
    
    def get_uid_kid(self,uid):
        kid_list = []
        sql = '''select b.kid from uinfo as a left join vsort as b on a.uname = b.uname where a.uid = %s''' 
        param = uid
        num = self.cursor.execute(sql,param) 
        raws = self.cursor.fetchall() 
        if num ==0 or num == None:
            return []
        else:
            for i in raws:
                kid_list.append(i[0])
            return kid_list
    
    def usum_exists(self,uid):
        sql = '''select uid from sta_usum where uid = "%s" ''' % (uid)
        print sql
        num = self.cursor.execute(sql)  
        if num ==0 or num == None:
            return False
        else:
            return True  
              
    def ugeo_exists(self,uid):
        sql = '''select uid from sta_ugeo where uid = "%s" ''' % (uid)
        print sql
        num = self.cursor.execute(sql)  
        if num ==0 or num == None:
            return False
        else:
            return True
        
    def get_uid_info(self,uid):
        ''' 从mongodb中获取用户的总共的统计数据。 '''
        uid_stat_t =  self.mongodbconn["video"]["%s_stat"%(uid)]
        
        uid_info_dir = uid_stat_t.find_one({"_id":uid})
        
        return uid_info_dir
    
    def get_user_email(self,uid):
        sql3 = "select email from uinfo where uid = %s"
        param = (uid)
        self.cursor.execute(sql3, param)
        self.mysqlconn.commit()
        row = self.cursor.fetchone()
        return row[0] 
    
    def get_ext_spaceinfo(self,uid):
        #获取ucurrenttc表中内容
        sql = 'select startdate,enddate,o_month_space,xufei_status,month_count from ucurrenttc where uid = %s'
        param = (uid)
        try:
            num = self.cursor.execute(sql,param)
            raws = self.cursor.fetchall() 
            if num ==0 or num == None:
                return []
            else:
                return  raws[0]           
        except Exception,e:            
            print "get_ext_typeinfo ,failure : ",e 
    
    def get_uid_playlist(self,uid):
        '''从mysql获取默认播放列表信息'''
        #sql = "select a.id,a.vid,a.vname,a.vform,a.preview_pic,a.preview_pic_form,a.vduration,a.description from vinfo as a left join uinfo as b on a.uname = b.uname where b.uid = %s order by a.playcount desc limit 4"
        sql = "select a.id,a.vid,a.vname,a.vform,a.preview_pic,a.preview_pic_form,a.vduration,a.description from vinfo as a left join uinfo as b on a.uname = b.uname where b.uid = %s and (a.vstatus = '23' or a.vstatus = 34) order by a.playcount desc limit 4"
        self.cursor.execute(sql,(uid))
        return self.cursor.fetchall()        

    def get_upid_info(self,upid):
        sql = 'select a.id,a.vid,a.vname,a.vform,a.preview_pic,a.preview_pic_form,a.vduration,a.description from vinfo as a left join uplist_vid as b on a.vid = b.vid where b.upid = %s '
        num = self.cursor.execute(sql,upid) 
        self.mysqlconn.commit() 
        if num ==0 or num == None:
            return []
        else:
            return self.cursor.fetchall()        
        
    def get_playinfo(self,uid):
        play_list = []
        sql = 'select a.upid from uplist as a left join uinfo as b on a.uname = b.uname where b.uid = %s'
        num = self.cursor.execute(sql,uid)
        self.mysqlconn.commit() 
        if num ==0 or num == None:
            return []
        else:
            for i in self.cursor.fetchall():
                play_list.append(i[0])
        
        return play_list
   
    def get_freeuser_space(self):
        sql = 'select size_limited from uchar where tid = 2'
        self.cursor.execute(sql)
        self.mysqlconn.commit()
        return self.cursor.fetchall()[0][0]
    
    def get_used_vidinfo(self,uid):
        sql = 'select a.vid,a.vsize,a.playcount from vinfo as a left join uinfo as b on a.uname = b.uname where b.uid = %s'
        self.cursor.execute(sql,uid)
        self.mysqlconn.commit()
        return self.cursor.fetchall()
 
    def get_uid_spaceinfo(self,uid):
        uid_spaceinfo = []
        sql = '''select uid,startdate,enddate,month_count,total_space from uspace where uid = %s'''  
        num = self.cursor.execute(sql,(uid))
        raws =  self.cursor.fetchall()
        self.mysqlconn.commit()
        if num ==0 or num == None:
            return False
        else:
            return raws
 
    def update_spaceinfo(self,uid,freespace):
        sql = '''update uspace set enddate='0000-00-00',month_count=0,total_space=%s where uid=%s'''
        params = (freespace,uid)
        try:
            self.cursor.execute(sql,params)
            self.mysqlconn.commit()
            return True
        except Exception,e:
            print "updata failure:%s" % e

    def update_usum(self,uid,uid_info):
        if uid_info != None:
            uid_vid_sum = int(uid_info["Nvideo"])
            uid_load_sum = uid_info["Load"]
            uid_ip_sum = uid_info["IP"]
            uid_play_sum = uid_info["Play"]
            uid_click_sum = uid_info["Click"]
            uid_engage_sum = uid_info["Engage"]
            uid_triffic_sum = uid_info["Traffic"]
        
        if self.usum_exists(uid):
            sql = '''
                  update sta_usum set vnum=%s,loadnum=%s,play=%s,ip=%s,engage_rate=%s,click_rate=%s,traffic=%s where uid = %s
                   '''
            param = (uid_vid_sum,uid_load_sum,uid_play_sum,uid_ip_sum,uid_engage_sum,uid_click_sum,uid_triffic_sum,uid)
            try:
                self.cursor.execute(sql,param)
                self.mysqlconn.commit()
                return True
            except Exception,e:
                print "updata failure:%s" % e
        else:
            sql = '''
                     INSERT INTO sta_usum(uid,vnum,loadnum,play,ip,engage_rate,click_rate,traffic) values (%s,%s,%s,%s,%s,%s,%s,%s)
                      ''' 

            param = (uid,uid_vid_sum,uid_load_sum,uid_play_sum,uid_ip_sum,uid_engage_sum,uid_click_sum,uid_triffic_sum)
            print param
            try:
                self.cursor.execute(sql,param)
                self.mysqlconn.commit()
                return True
            except Exception,e:
                print "updata failure:%s" % e  
                          
    def update_ugeo(self,uid,uid_info):
        if uid_info != None:
            uid_geo_sum = uid_info["Geo"]
            area_date = json.dumps(uid_geo_sum)
            print area_date
        if self.ugeo_exists(uid):
            sql = '''
                    update sta_ugeo set area_date=%s where uid = %s
                    '''
            param = (area_date,uid)
            try:
                self.cursor.execute(sql,param)
                self.mysqlconn.commit()
                return True
            except Exception,e:
                print "updata failure:%s" % e
        else:
            sql = '''
                INSERT INTO sta_ugeo(uid,area_date) values (%s,%s)
                ''' 
            param = (uid,area_date)
            try:
                self.cursor.execute(sql,param)
                self.mysqlconn.commit()
                return True
            except Exception,e:
                print "updata failure:%s" % e
        
    def update_uspaceinfo(self,starttime,enddate,month_count,space,uid):
        sql = '''update uspace set startdate=%s,enddate=%s,month_count=%s,total_space=%s where uid = %s'''
        params = (starttime,enddate,month_count,space,uid)
        try:
            self.cursor.execute(sql,params)
            self.mysqlconn.commit()
            return True
        except Exception,e:
            print "updata failure:%s" % e     
            return False         

    def del_vid(self,vid):  
        sql = 'delete from vinfo where vid = %s'
        self.cursor.execute(sql,vid)
        self.mysqlconn.commit()        

    
class VidInfo(object):
    '''
           class VidInfo
           functions     get_vid_kid     how mush did this vid have kids.return the number and kid list
                         get_vid_info    get vid info from mongodb
                         vsum_exists     does table sta_vsum existed in video database.
                         vgeo_exists     does table stat_vgeo existed in video database.
                         vhmap_exists    does table stat_vhmap existed in video database.
                         update_vsum     update table sta_vsum 
                         update_vgeo     update table sta_vgeo
                         updata_vhmap    update table sta_vhmap
    '''
    def __init__(self,mysqlconn,mongodbconn,vid):
        self.vid = vid
        
        self.mysqlconn = mysqlconn
                
        self.mongodbconn = mongodbconn
                
        self.cursor = self.mysqlconn.cursor()        
    
    def get_vid_kid(self,vid):
        
        sql = '''
               select b.kid from vinfo as a left join vsort as b on a.vsortid = b.id where a.vid = %s
              '''
        param = vid
        
        num = self.cursor.execute(sql,param)
        
        raws = self.cursor.fetchall()
        
        if num == 0 or num == None:
            return None
        else:
            return int(num),raws[0][0]
        
    def get_vid_info(self,vid):
        ''' 从mongodb中获取vid的总共的统计数据。 '''
        uid = vid[0:4]
        uid_stat_t =  self.mongodbconn["video"]["%s_stat"%(uid)]
            
        vid_info_dir = uid_stat_t.find_one({"_id":vid})
            
        return vid_info_dir   
    
    def get_uid_playlist(self,vid):
        uid = vid[0:4]
        '''从mysql获取默认播放列表信息'''
        #sql = "select a.id,a.vid,a.vname,a.vform,a.preview_pic,a.preview_pic_form,a.vduration,a.description from vinfo as a left join uinfo as b on a.uname = b.uname where b.uid = %s order by a.playcount desc limit 4"
        sql = "select a.id,a.vid,a.vname,a.vform,a.preview_pic,a.preview_pic_form,a.vduration,a.description from vinfo as a left join uinfo as b on a.uname = b.uname where b.uid = %s and (a.vstatus = '23' or a.vstatus = 34) order by a.playcount desc limit 4"
        self.cursor.execute(sql,(uid))
        return self.cursor.fetchall()

    def vsum_exists(self,vid):
        sql = '''select vid from sta_vsum where vid = "%s" ''' % (vid)
        print sql
        num = self.cursor.execute(sql)  
        if num ==0 or num == None:
            return False
        else:
            return True         
      
    def vgeo_exists(self,vid):
        sql = '''select vid from sta_vgeo where vid = "%s" ''' % (vid)
        print sql
        num = self.cursor.execute(sql)  
        if num ==0 or num == None:
            return False
        else:
            return True 
        
    def vhmap_exists(self,vid):
        sql = '''select vid from sta_vhmap where vid = "%s" ''' % (vid)
        print sql
        num = self.cursor.execute(sql)  
        if num ==0 or num == None:
            return False
        else:
            return True
      
    def update_vsum(self,vid,vid_info):
        if vid_info != None:
            uid = vid[0:4]
            loadnum = vid_info["Load"]
            play = vid_info["Play"]
            ip = vid_info["IP"]
            engage_rate = vid_info["Engage"]
            click_rate = vid_info["Click"]
            traffic = vid_info["Traffic"]
        
        if self.vsum_exists(vid):
            sql = '''
                    update sta_vsum set loadnum=%s,play=%s,ip=%s,engage_rate=%s,click_rate=%s,traffic=%s where vid = %s
                   '''
            param = (loadnum,play,ip,engage_rate,click_rate,traffic,vid)
            try:
                self.cursor.execute(sql,param)
                self.mysqlconn.commit()
                return True
            except Exception,e:
                print "UPdate vid info failure,%s" % e
                
        else:
            sql = '''
                     insert into sta_vsum (vid,uid,loadnum,play,ip,engage_rate,click_rate,traffic) values (%s,%s,%s,%s,%s,%s,%s,%s)
                    '''
            param = (vid,uid,loadnum,play,ip,engage_rate,click_rate,traffic)
            try:
                self.cursor.execute(sql,param)
                self.mysqlconn.commit()
                return True
            except Exception,e:
                print "UPdate vid info failure,%s" % e 
                
    def update_vgeo(self,vid,vid_info):
        if vid_info != None:
            uid = vid[0:4]
            geo = vid_info["Geo"]
            area_date = json.dumps(geo)
        if self.vgeo_exists(vid):
            sql = '''
                     update sta_vgeo set area_date=%s where vid=%s
                    '''
            param = (area_date,vid)
            try:
                self.cursor.execute(sql,param)
                self.mysqlconn.commit()
                return True
            except Exception,e:
                print "update vgeo info failure,%s" % e
        else:
            sql = '''
                    insert into sta_vgeo (vid,uid,area_date) values (%s,%s,%s)
                  '''
            param = (vid,uid,area_date)
            try:
                self.cursor.execute(sql,param)
                self.mysqlconn.commit()
                return True
            except Exception,e:
                print "insert vgeo info failure,%s" % e
            
    def update_vhmap(self,vid,vid_info):
        if vid_info != None:
            uid = vid[0:4]
            htmap = vid_info["Htmap"]
            map = json.dumps(htmap)
        if self.vgeo_exists(vid):
            sql = '''
                     update sta_vhmap set map=%s where vid=%s
                '''
            param = (map,vid)
            try:
                self.cursor.execute(sql,param)
                self.mysqlconn.commit()
                return True
            except Exception,e:
                print "update vhmap info failure,%s" % e
        else:
            sql = '''
                insert into sta_vhmap (vid,uid,map) values (%s,%s,%s)
                '''
            param = (vid,uid,map)
            try:
                self.cursor.execute(sql,param)
                self.mysqlconn.commit()
                return True
            except Exception,e:
                print "insert vhmap info failure,%s" % e      
                          
class KidInfo(object):
    '''
         class KidInfo
         function     ksum_exists     does table sta_ksum exist in video database
                      kgeo_exists     does table sta_kgeo exist in video database
                      get_kid_info    get kid info from mongodb
                      update_ksum     update table sta_ksum
                      update_kgeo     update table sta_kgeo
                    
    '''
    def __init__(self,mysqlconn,mongodbconn,kid):
        self.kid = kid
            
        self.mysqlconn = mysqlconn
                    
        self.mongodbconn = mongodbconn
                    
        self.cursor = self.mysqlconn.cursor()       
    
    def ksum_exists(self,kid):
        sql = ''' select kid from sta_uksum where kid = %s'''
        param = kid
        num = self.cursor.execute(sql,param)  
        
        if num ==0 or num == None:
            return False
        else:
            return True  
        
    def kgeo_exists(self,kid):
        sql = ''' select kid from sta_ukgeo where kid = %s'''
        param = kid
        num = self.cursor.execute(sql,param)  
        if num ==0 or num == None:
            return False
        else:
            return True
    
    def get_kid_info(self,kid):
        uid = kid[0:4]
        uid_stat_t =  self.mongodbconn["video"]["%s_stat"%(uid)]
                    
        kid_info_dir = uid_stat_t.find_one({"_id":kid})
                    
        return kid_info_dir  
    
    def update_ksum(self,kid,kid_info):
        if kid_info != None:
            uid = kid[0:4]
            loadnum = kid_info["Load"]
            play = kid_info["Play"]
            ip = kid_info["IP"]
            engage_rate = kid_info["Engage"]
            click_rate = kid_info["Click"]
            traffic = kid_info["Traffic"]   
            
        if self.ksum_exists(kid):
            sql = '''
                    update sta_uksum set loadnum=%s,play=%s,ip=%s,engage_rate=%s,click_rate=%s,traffic=%s where kid = %s
                    '''
            param = (loadnum,play,ip,engage_rate,click_rate,traffic,kid)
            try:
                self.cursor.execute(sql,param)
                self.mysqlconn.commit()
                return True
            except Exception,e:
                print "UPdate ksum info info failure,%s" % e
                         
        else:
            sql = '''
                    insert into sta_uksum (kid,uid,loadnum,play,ip,engage_rate,click_rate,traffic) values (%s,%s,%s,%s,%s,%s,%s,%s)
                    '''
            param = (kid,uid,loadnum,play,ip,engage_rate,click_rate,traffic)
            try:
                self.cursor.execute(sql,param)
                self.mysqlconn.commit()
                return True
            except Exception,e:
                print "insert  kid sum info failure,%s" % e  
         
    def update_kgeo(self,kid,kid_info):
        if kid_info != None:
            uid = kid[0:4]
            geo = kid_info["Geo"]
            area_date = json.dumps(geo)
        if self.kgeo_exists(kid):
            sql = '''
                    update sta_ukgeo set area_date=%s where kid=%s
                    '''
            param = (area_date,kid)
            try:
                self.cursor.execute(sql,param)
                self.mysqlconn.commit()
                return True
            except Exception,e:
                print "update ukgeo info failure,%s" % e
        else:
            sql = '''
                    insert into sta_ukgeo (kid,uid,area_date) values (%s,%s,%s)
                    '''
            param = (kid,uid,area_date)
            try:
                self.cursor.execute(sql,param)
                self.mysqlconn.commit()
                return True
            except Exception,e:
                print "insert ukgeo info failure,%s" % e  
                
       

class TypeInfo(object):
    def __init__(self,mysqlconn,typeid):
        self.typeid = typeid
        self.cursor = mysqlconn.cursor()
        self.raw_list = self.get_type_info()
        if self.raw_list != None:
            self.flow = self.raw_list[0]
            self.month = self.raw_list[0]
        else:
            self.flow = None
            self.month = None
            
    def get_type_info(self):
        sql = 'select flow_limited,number_limited from uchar where tid = %s'
        param = (self.typeid)
        try:
            self.cursor.execute(sql,param)
            raws = self.cursor.fetchall() 
            if raws ==0 or raws == None:
                return []
            else:
                return  raws[0]           
        except Exception,e:
            print "UPdate vid info failure,%s" % e        
        
    
    def get_flow(self):
        return self.flow
    
    def get_month(self):
        return self.month               

    def get_ext_typeinfo(self,uid):
        sql = 'select startdate,enddate,o_month_flow,xufei_status,month_count from ucurrenttc where uid = %s'
        param = (uid)
        try:
            num = self.cursor.execute(sql,param)
            raws = self.cursor.fetchall() 
            if num ==0 or num == None:
                return []
            else:
                return  raws[0]           
        except Exception,e:            
            print "get_ext_typeinfo ,failure : ",e
