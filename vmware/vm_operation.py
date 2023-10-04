#!/usr/bin/env python3

"""
  Description:
  
  This python script allows user to clone one or multiple VMWare ESXi virtual machines 
  based on existing template. This python script uses the python module "vmwarevms.py" 
  to implement the detailed virtual machine deployment. For the detailed information
  regarding python module "vmwarevms.py", please check this python script 'vmwarevms.py". 
  To get the help menu of this script, please run "python3 vm_operation.py -h" to get 
  a detailed description on how to use this script.  
"""

import sys
import argparse
import logging
import re
import time
import yaml

from autoutil import *
from vmwarevms import vms

def _get_ip_from_range(ip_range, vm_ips, mylogger):
    ip_range = ip_range.replace(" ", "")
    if(re.search(r'-', ip_range, re.M|re.I) == None):   # search if ip is like "192.168.0.41--51"
        vm_ips.append(ip_range)
        return 0

    ip_list = re.split('-+', ip_range)      # ip_range is like "192.168.0.41--51" 
    if(len(ip_list) != 2):                  # ip_list should be ['192.168.0.41', '51'] or ['192.168.0.41', '192.168.0.51']
        mylogger.warning("Please provide a valid virtual machine IP address or range: %s" % ip_range)
        return 1

    start_ip = ip_list[0]
    last_ip = ip_list[1]
    if( len(ip_list[1]) <= 3 ):
        last_ip = re.sub('\d+$', ip_list[1], start_ip)

    from ipaddress import ip_address
    start_int = int(ip_address(start_ip).packed.hex(), 16)
    last_int = int(ip_address(last_ip).packed.hex(), 16)
    tmp_ip = [ip_address(ip).exploded for ip in range(start_int, last_int + 1)]

    for ip in tmp_ip:
        vm_ips.append(ip)

    return 0


def get_vm_ip(vc_name, vc_user, vc_pw, vc_ssl_check, mylogger, vm_list):
    vm_ips = []
    vms_obj = vms(vc_name = vc_name, vc_user = vc_user, vc_pw = vc_pw, vc_ssl_check = vc_ssl_check, logger = mylogger)
    vms_ips = vms_obj.get_vm_ip(vm_list)
    return vms_ips


def create_from_yaml(yamlfile, yaml_section, mylogger, deplogfile):
    vcdata = {}
    with open(yamlfile, "r") as file_descr:
        yaml_item = yaml.load(file_descr, Loader=yaml.FullLoader)

    vcenter_items = yaml_item.get("VCenter")
    vm_cluster = yaml_item.get(yaml_section)

    for key in vcenter_items.keys():
        vcdata[key] = vcenter_items[key]

    if( vcdata["snapshot_name"] == "None" ): vcdata["snapshot_name"] = None
    if( "hostname_update" not in vcdata.keys() ): vcdata["hostname_update"] = False
    vcdata["deployed_vm"] = []

    base_vm = vcdata["base_vmname"]
    for item in vm_cluster:
        vm_ips = []
        cluster_data = {}
        if( re.search("-\[date\]", base_vm, re.M|re.I) != None ):
            base_vmname = base_vm.replace("-[date]", "")
            base_vmname = base_vmname + "-" + str(int(time.time()))

        for key in item.keys():
            value = item[key]
            if(re.search(r'ip', key, re.M|re.I) != None ):
                _get_ip_from_range(value, vm_ips, mylogger)
            else:
                cluster_data[key] = value 

        static_ip = False if("dhcp" in vm_ips or "DHCP" in vm_ips) else True
        if( "cluster" not in cluster_data.keys() ): cluster_data["cluster"] = None
        if( "esx" not in cluster_data.keys() ): cluster_data["esx"] = None
    
        vms_obj = vms(vc_name = vcdata["vcenter_name"], vc_user = vcdata["vcenter_user"], vc_pw = vcdata["vcenter_pw"], vc_ssl_check = vcdata["ssl-check"],
                      base_vmname = base_vmname, count = cluster_data["vm_count"], template = cluster_data["template"], vm_user = cluster_data["vm_user"],
                      vm_password = cluster_data["vm_password"], hostname_update = vcdata["hostname_update"], data_center = vcdata["datacenter"],
                      folder = vcdata["folder"], cluster = cluster_data["cluster"], esx = cluster_data["esx"], data_store = cluster_data["datastore"],
                      network = cluster_data["network"], static_ip = static_ip, power_on = vcdata["power_on"], snapshot_name = vcdata["snapshot_name"],
                      logger = mylogger, tmplogfile = deplogfile)  

        if(static_ip == True):
            if( cluster_data["vm_count"] != len(vm_ips) ):
                mylogger.warning("There are %d IP address defined in YAML section %s for cluster %s. That does not equal to the defined vm_count %d in file %s. "
                                 "Unable to create VMs." % (len(vm_ips), yaml_section, cluster_data["cluster"], cluster_data["vm_count"], yamlfile))
                return (1, vcdata)

            vms_obj.set_static_ip(vm_ips, cluster_data["netmask"], cluster_data["gateway"], cluster_data["dns"])

        try:
            rc = vms_obj.deploy_vm()
            if(rc != 0):
                mylogger("Error creating virtual machine for YAML section %s, cluster %s in file %s" % (yaml_section, cluster_data["cluster"], yamlfile))
                return (rc, vcdata)
        except Exception as exp:
            mylogger.warning("Catching exception while deploying virtual machines. Exception details: %s" % exp)
            return (1, vcdata)

        for vm in vms_obj.deployed_vm:
            vm_detail = {}
            vm_detail["vm_name"] = vm
            vm_detail["vm_user"] = cluster_data["vm_user"]
            vm_detail["vm_password"] = cluster_data["vm_password"]
            vcdata["deployed_vm"].append(vm_detail)

        if( re.search("-\[date\]", base_vm, re.M|re.I) != None ):  #base_vm is "vm-[date]"
            continue
        tmp_vm_list = build_vmname(base_vm, cluster_data["vm_count"] + 1)
        base_vm = tmp_vm_list[-1]

    return (0, vcdata)    # all the specified vms have been successfully deployed here


def main(argv):
    #get script parameter arguments
    parser = argparse.ArgumentParser()

    parser.add_argument('-yf', '--yamlfile', required=False, help='YAML file', dest='yamlfile', type=str)
    parser.add_argument('-ys', '--yamlsection', required=False, help='YAML file section', dest='yamlsection', type=str)
    parser.add_argument('-l', '--loglevel', nargs=1, required=False, help='Log Level. Default is INFO', dest='loglevel', type=str)
    parser.add_argument('-o', '--outlogfile', nargs=1, required=False, help='Output Log File Name. Default is vm_oper_$date.log', dest='outlogfile', type=str)

    args = parser.parse_args()
    yamlfile = args.yamlfile
    yaml_section = args.yamlsection

    if not args.loglevel:
        loglevel = logging.INFO
    else:
        if args.loglevel[0].upper() == 'DEBUG':
            loglevel = logging.DEBUG
        elif args.loglevel[0].upper() == 'INFO':
            loglevel = logging.INFO
        elif args.loglevel[0].upper() == 'WARNING':
            loglevel = logging.WARNING
        else:
            print('The input loglevel is not right. Please choose among DEBUG, INFO, WARNING')
            sys.exit(1)

    if not args.outlogfile:
        outlogfile = 'vm_operation_' + time.strftime('%Y_%m_%d_%H_%M_%S', time.localtime()) + '.log'
    else:
        outlogfile = args.outlogfile[0]

    deplogfile = outlogfile + '_dep'

    # configure logging levels
    logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)s {%(module)s} [%(funcName)s] %(message)s', 
                        datefmt='%Y-%m-%d %H:%M:%S', level=loglevel,
                        handlers=[logging.FileHandler(outlogfile), logging.StreamHandler()])

    mylogger = logging.getLogger(__name__)
    # start operation
    mylogger.info('Start Operation')

    (rc, vcdata) = create_from_yaml(yamlfile, yaml_section, mylogger, deplogfile)

    return rc

if __name__ == "__main__":
    rc = main(sys.argv[1:])
    sys.exit(rc)
