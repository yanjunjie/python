#!/bin/sh
squidcache_path="/home/squid"
squidclient_path="/usr/bin/squidclient"

RawUrls=$1

if [ "X$RawUrls" = "X" ]; then
   echo "ERROR : PLEASE INPUT URL FOR FLUSH SQUID CACHE!"
   exit 1
fi

UrlStr=`echo $RawUrls | awk -F"#" '{split($1,myarr,"|") ;for(i in myarr){print myarr[i]}}'`

echo $UrlStr

UrlArray=( $UrlStr )

UrlsNum=${#UrlArray[*]}

for ((i=0;i<$UrlsNum;i++))
do
   UrlAddr=${UrlArray[i]}
   sflag=${UrlAddr:(-4):1}
   if [ $sflag == "." ]; then
      echo $UrlAddr > cache_list.txt
   else
      echo "xiha"
      grep -a -r $UrlAddr  $squidcache_path/* | strings | grep "http:" |awk -F"http:" '{print "http:"$2;}'> cache_list.txt   
   fi
   for url in `cat cache_list.txt`; do
      if [ `expr index $url "?"` -eq 0 ]; then
         echo $url
         echo "123"
         $squidclient_path -m PURGE -p 80 "$url"
         echo "456"
      fi
   done
done

exit 0
