#-*- encoding:utf-8 -*-

'''
Created on 2012-11-15

@author: root
'''

print "hello world ,'jack'"

print "hello world,\"jack\""

print " jack  \
        terry \
        luay  \
      "
      
print """ jack
          terry 
          luay
      """
      
uname = "Linux #1 SMP Tue Feb"

print "Linux" in uname
print "Linux" not in uname

print uname.find("SMP")
print uname.index("SMP")

SMP_index = uname.index("SMP")
print uname[SMP_index:]
print uname[:SMP_index]

print uname.startswith("Linux")
print uname.endswith("Feb1")

#切分技术实现startswith和endswith

if uname[:len("Linux")] == "Linux":
    print True
else:
    print False

#lstrip,rstrip,strip不只是被用来删除前后空格

xml_tag = "<some_tag>"
print xml_tag.lstrip("<")
print xml_tag.rstrip(">")

print xml_tag.strip("<>")


