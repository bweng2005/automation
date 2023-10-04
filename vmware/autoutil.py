import time
import sys
import os
import re

__all__ = ['build_vmname', 'writelog']

# Build several virtual machines name based on "base_vmname" and the count.
# The virtual machine names are saved in a list and returned to caller.
#
def build_vmname(base_vmname, count):

    # build virtual machine names
    vm_list = []
    start_num, start_zero = '', ''

    searchObj = re.search( r'(\d+$)', base_vmname, re.M|re.I)    # base_vmname is 'vm-00212' or 'vm-212' or 'vm-1625573421'
    if searchObj:
        start_num = searchObj.group(1)                           # start_num is '00212' or '212'
        start_vmnum = start_num                                  # start_vmnum is '00212' or '212'
        start_vmname = base_vmname[0:searchObj.start()]          # start_vmname is 'vm-'
        fill_len = len(start_vmnum)                              # for '0' fill up length 

        searchObj1 = re.search( r'(^0*)', start_num, re.M|re.I)  # find leading zero
        if searchObj1:
            start_zero = searchObj1.group(1)                     # start_zero is '00'
            start_vmnum = start_num[searchObj1.end():]           # start_vmnum is '212'
            #start_vmname = start_vmname + start_zero            # start_vmname is 'vm-00'

        start_vmnum = int(start_vmnum)
        for i in range(count):
            vmnum = start_vmnum + i
            if(vmnum > 10000):
                vmnum = time.strftime('%m%d%H%M%S', time.localtime(vmnum)) # for base_vmname is 'vm-1625573421'
            else:
                vmnum = str(vmnum).zfill(fill_len)                         # for '00212', fill up to '00213'. No impact on 213
            vm_name = start_vmname + str(vmnum)
            vm_list.append(vm_name)

    return vm_list

# Write log message to a log file. User can specify whether to include timestamp in the log message.
#
def writelog(logfile_name, logmsg, writetime = True):
    mypid = os.getpid()
    msg = logmsg
    if(writetime == True):
        msg = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' {%s}' % sys.argv[0] + '{PID: %d} ' % mypid + logmsg
    logfile = open(logfile_name, 'a')
    logfile.write('%s\n' % msg)
    logfile.close()

