#-*- encoding:utf-8 -*-

import gdchart
import shelve

def chartBar():
    shelve_file = shelve.open("File/BytesSumPerHost.bat")

    #元组列表
    items_list = [(i[1],i[0]) for i in shelve_file.items()]
    items_list.sort()

    bytes_sent = [i[0] for i in items_list]
    ip_addresses = [i[1] for i in items_list]

    chart = gdchart.Bar() 
    chart.width = 400
    chart.height = 400
    chart.bg_color = "white"
    chart.plot_color = "black"
    chart.xtitle = "IP ADDRESS"
    chart.ytitle = "Bytes Sent"
    chart.title = "Usage bytes by ip address"
    chart.setData(bytes_sent)
    chart.setLabels(ip_addresses)
    chart.draw("File/bytes_ip_adr.png")
    shelve_file.close()

#chartBar()

import itertools
def chartPie():
    shelve_file = shelve.open("File/BytesSumPerHost.bat")
    #items_list = [(i[1],i[0]) for i in shelve_file.items() if i[1]>0]
    items_list = [(i[1],i[0]) for i in shelve_file.items()]
    items_list.sort()
    bytes_sent = [i[0] for i in items_list]
    print bytes_sent
    ip_addresses = [i[1] for i in items_list]
    print ip_addresses
    chart = gdchart.Pie()
    chart.width = 400
    chart.height = 400
    chart.bg_color = 'white'
    color_cycle = itertools.cycle([0xDDDDDD,0x111111,0x777777])
    color_list = []
    for i in bytes_sent:
        color_list.append(color_cycle.next())
    chart.color = color_list
    chart.plot_color = 'black'
    chart.title = "Usage By Ip Address"
    chart.setData(12, 12, 24, 48, 140)
    chart.setLabels(ip_addresses)
    chart.draw("File/bytes_ip_pie.png")

    shelve_file.close()    
    
chartPie()    
   
    
    
    
    
    