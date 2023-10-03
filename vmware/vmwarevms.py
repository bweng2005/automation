#!/usr/bin/env python3

"""
  Description:
  
  This python script allows user to use VMware vCenter to clone one or multiple
  virtual machines based on existing template. User can also create snapshots or
  delete virtual machines. This script can perform the following operations:
      Deploy one or many virtual machines
      Deploy the virtual machines in a designated datacenter
      Deploy the virtual machines in a designated datastore
      Deploy the virtual machines in a designated cluster
      Deploy the virtual machines in a designated ESXi server
      Create snapshots 
      Delete one or many virtual machines
  To run this script, user needs to download the VMware vSphere Python SDK(pyVmomi)
  into the running machine.
  
"""

import sys
import argparse
import atexit
import logging
import re
import copy
import time

from autoutil import *

from pyVim.connect import SmartConnect, SmartConnectNoSSL, Disconnect
from pyVmomi import vim, vmodl

class vms:
    def __init__(self, vc_name = None, vc_user = None, vc_pw = None, vc_ssl_check = False, vc_port = 443, base_vmname = None, count = 1, template = None,
                 vm_user = None, vm_password = None, hostname_update = False, data_center = None, folder = None, cluster = None, esx = None, data_store = None, 
                 network = None, network_vds = True, static_ip = False, power_on = True, snapshot_name = None, logger = None, tmplogfile = None):
 
        # initialize class object values
        self.vc_name = vc_name
        self.vc_user = vc_user
        self.vc_pw = vc_pw
        self.vc_ssl_check = vc_ssl_check
        self.vc_port = vc_port
        self.base_vmname = base_vmname
        self.count = count
        self.template = template
        self.vm_user = vm_user
        self.vm_password = vm_password
        self.hostname_update = hostname_update
        self.data_center = data_center
        self.folder = folder
        self.cluster = cluster
        self.esx = esx
        self.data_store = data_store
        self.network = network
        self.network_vds = network_vds
        self.static_ip = static_ip
        self.power_on = power_on
        self.snapshot_name = snapshot_name
        self.logger = logger
        self.tmplogfile = tmplogfile

        self.conn_obj = None
        self.conn_content = None
        self.template_obj = None
        self.folder_obj = None
        self.vm_spec = None
        self.vm_ostype = None

        self.vm_list = []
        self.static_ip_list = []
        self.vm_netmask = None 
        self.vm_gateway = None 
        self.vm_dns = None 

        if(self.base_vmname != None):
            tmp_vm_list = build_vmname(self.base_vmname, self.count)
            self.vm_list = copy.deepcopy(tmp_vm_list)
        self.deployed_vm = []  #not every vm in self.vm_list can be deployed


    # set up VMs static ip information
    #
    def set_static_ip(self, iplist, netmask, gateway, dns):
        for ip in iplist:
            self.static_ip_list.append(ip)
        self.vm_netmask = netmask
        self.vm_gateway = gateway
        self.vm_dns = dns


    # check whether static IP setup for virtual machine succeeds
    #
    def check_static_ip(self):
        self.logger.info("Checking static IP setup for virtual machine")

        timeout = int(time.time()) + 3600
        while( int(time.time()) < timeout ):
            self.logger.info('-'*15 + "Waiting for static IP setup for virtual machine" + '-'*15)
            vm_ips = self.get_vm_ip()    #   in the format of [{'vm_name': 'vm1', 'vm_ip': '192.168.51.x'},,]

            boot_vm_ips = []
            for vm in vm_ips:
                if( vm["vm_ip"] != None and len(vm["vm_ip"]) > 0 ):
                    boot_vm_ips.append(vm["vm_ip"])

            count = 0
            for ip in self.static_ip_list:
                if(ip in boot_vm_ips):
                    count = count + 1 

            if(count == len(self.static_ip_list)):
                self.logger.info("The static IP setup is completed for all the VMs")
                return 0
            self.logger.info("The static IP setup is still not completed for all the VMs")
            time.sleep(30)
                
        self.logger.warning("The static IP setup can not be completed for all the VMs within one hour")
        return 1


    # locate object from vCenter by calling vSphere API
    #
    def locate_obj(self, name, vimtype):
        content = self.conn_content
        vcobj_view = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
        vcobj_list = vcobj_view.view
        ret_obj = None

        for obj in vcobj_list:
            if obj.name == name:
                self.logger.debug('Found object %s' % name)
                ret_obj = obj
                break

        vcobj_view.Destroy()
        return ret_obj 


    # connect to vCenter
    #
    def connect_vc(self):
        try:
            if(self.vc_ssl_check == False):
                self.conn_obj = SmartConnectNoSSL(host=self.vc_name, user=self.vc_user, pwd=self.vc_pw, port=self.vc_port)
            else:
                self.conn_obj = SmartConnect(host=self.vc_name, user=self.vc_user, pwd=self.vc_pw, port=self.vc_port)

            atexit.register(Disconnect, self.conn_obj)
            self.logger.debug('Registering disconnect at script exit')
        except IOError as error:
            self.logger.warning('Having ioerror while connecting to vcenter %s. Error: %s' % (self.vc_name, error)) 
        except Exception as exp:
            self.logger.warning('Having problem while connecting to vcenter %s. Exception: %s' % (self.vc_name, exp))

        if not self.conn_obj:
            self.logger.warning('Can not connect to VCenter %s' % self.vc_name)
            return 1
        else:
            self.conn_content = self.conn_obj.RetrieveContent()
            return 0 


    # build specifictions to deploy virtual machines
    #
    def build_vm_spec(self):
        self.logger.info('Start building virtual machine speficication')

        # connect to vCenter first
        rc = self.connect_vc()
        if(rc == 1):
            self.logger.info('Error connecting to vCenter %s' % self.vc_name)
            return rc 

        # locate the user specified template
        self.logger.debug('Trying to get template %s details' % self.template)
        self.template_obj = self.locate_obj( str(self.template), [vim.VirtualMachine] )
        if not self.template_obj:
            self.logger.warning('Unable to retrieve template %s' % self.template)
            return 1
        self.logger.info('Successfully retrieve template %s from vCenter' % self.template)

        # locate the Datacenter
        data_center = None
        if self.data_center:
            data_center = self.locate_obj( str(self.data_center), [vim.Datacenter] )
            if not data_center:
                self.logger.warning('Unable to retrieve data center %s' % self.data_center)
                return 1
            self.logger.info('Successfully retrieve data center %s' % self.data_center)

        # locate the Cluster or ESX host. locate their Resource Pool accordingly
        #
        cluster, esxhost, resource_pool = None, None, None
        if self.cluster:
            cluster = self.locate_obj( str(self.cluster), [vim.ClusterComputeResource] )
            if not cluster:
                self.logger.warning('Unable to retrieve cluster %s' % self.cluster)
                return 1
            self.logger.info('Successfully retrieve cluster %s' % self.cluster)

            resource_pool = cluster.resourcePool
            if not resource_pool:
                self.logger.warning('Unable to retrieve resource pool from cluster %s' % self.cluster)
                return 1
            self.logger.info('Successfully retrieve resource pool from cluster %s' % self.cluster)
        elif self.esx:
            esxhost = self.locate_obj( str(self.esx), [vim.HostSystem] )
            if not esxhost:
                self.logger.warning('Unable to retrieve ESX host %s' % self.esx)
                return 1
            self.logger.info('Successfully retrieve ESX host %s' % self.esx)

            resource_pool = esxhost.parent.resourcePool
            if not resource_pool:
                self.logger.warning('Unable to retrieve resource pool from ESX host %s' % self.esx)
                return 1
            self.logger.info('Successfully retrieve resource pool from ESX host %s' % self.esx)
        else:
            cluster = self.template_obj.summary.runtime.host.parent
            if not cluster:
                self.logger.warning('Unable to retrieve cluster from template %s ESX host' % self.template)
                return 1
            self.logger.info('Successfully retrieve cluster from template %s ESX host' % self.template)

            resource_pool = cluster.resourcePool
            if not resource_pool:
                self.logger.warning('Unable to retrieve resource pool from template %s ESX host' % self.template)
                return 1
            self.logger.info('Successfully retrieve resource pool from template %s ESX host' % self.template)

        # locate the Folder
        folder = None
        if self.folder:
            folder = self.locate_obj( str(self.folder), [vim.Folder] )
            if not folder:
                self.logger.warning('Unable to retrieve folder %s' % self.folder)
                return 1
            self.logger.info('Successfully retrieve folder %s' % self.folder)
        elif data_center:
            folder = data_center.vmFolder
        else:
            folder = self.template_obj.parent
        self.folder_obj = folder

        if not folder:
            self.logger.warning('Unable to retrieve folder from either datacenter or template')
            return 1

        # locate the datastore
        data_store = None
        if self.data_store:
            data_store = self.locate_obj( str(self.data_store), [vim.Datastore] )
            if not data_store:
                self.logger.warning('Unable to retrieve data store %s', self.data_store)
                return 1
            self.logger.info('Successfully retrieve datastore %s' % self.data_store)
        else:
            data_store = self.locate_obj( self.template_obj.datastore[0].info.name, [vim.Datastore] )
            if not data_store:
                self.logger.warning('Unable to retrieve datastore from template %s' % self.template)
                return 1
            self.logger.info('Successfully retrieve datastore from template %s' % self.template)

        # create place holder for specifications
        relocate_spec = vim.vm.RelocateSpec()
        if resource_pool:
            relocate_spec.pool = resource_pool
        if data_store:
            relocate_spec.datastore = data_store

        power_state = False

        self.vm_spec = vim.vm.CloneSpec(powerOn=power_state, template=False, location=relocate_spec)

        self.logger.info('Done with building virtual machine speficication')
        return 0 
        # done with build_vm_spec


    # migrate virtual machine to user specified ESXi host
    #
    def relocate_vm(self):
        self.logger.info('Start relocating virtual machine to the specified ESXi host')

        esxhost = self.locate_obj( str(self.esx), [vim.HostSystem] )
        if not esxhost:
            self.logger.warning('Unable to retrieve ESX host %s' % self.esx)
            return 1
        resource_pool = esxhost.parent.resourcePool
        if not resource_pool:
            self.logger.warning('Unable to retrieve resource pool from ESX host %s' % self.esx)
            return 1

        vm_relocated = {}
        vm_result = {}
        task_msg = 'Virtual machine ESX host relocating'
        for vm_name in self.vm_list:
            tmp_vm = self.locate_obj(vm_name, [vim.VirtualMachine])
            if not tmp_vm:
                self.logger.warning('Unable to find virtual machine %s from vcenter %s' % (vm_name, self.vc_name))
                return 1

            spec = vim.VirtualMachineRelocateSpec()
            spec.host = esxhost
            spec.pool = resource_pool
            
            task = tmp_vm.RelocateVM_Task(spec)
            vm_relocated[vm_name] = task

        rc = self.wait_task_finish(vm_relocated, vm_result, task_msg, 3600)
        if(rc != 0):
            self.logger.warning('Unable to finish virtual machine ESX host updating within one hour')
            return rc

        cluster = esxhost.parent
        if(re.search(r'ClusterComputeResource', str(cluster), re.M|re.I) == None):
            return rc
        #the ESX host is not within a cluster

        # need to disable vm's DRS migration to avoid automatic vmotion
        self.logger.info('Start updating virtual machine DRS migration') 
        time.sleep(15)
        vm_updated = {}
        vm_result = {}
        task_msg = 'Virtual machine DRS migration updating' 
        for vm_name in self.vm_list:
            tmp_vm = self.locate_obj(vm_name, [vim.VirtualMachine])
            if not tmp_vm:
                self.logger.warning('Unable to find virtual machine %s from vcenter %s' % (vm_name, self.vc_name))
                return 1

            drs_vm_config_info = vim.cluster.DrsVmConfigInfo()
            drs_vm_config_info.key = tmp_vm
            drs_vm_config_info.enabled = False
            drs_vm_config_info.behavior = vim.cluster.DrsConfigInfo.DrsBehavior.manual

            drs_config_spec = vim.cluster.DrsVmConfigSpec()
            drs_config_spec.operation = vim.option.ArrayUpdateSpec.Operation.add
            drs_config_spec.info = drs_vm_config_info
            cluster_spec_ex = vim.cluster.ConfigSpecEx()
            cluster_spec_ex.drsVmConfigSpec = [drs_config_spec]

            task = cluster.ReconfigureComputeResource_Task(cluster_spec_ex, True)
            vm_updated[vm_name] = task

        rc = self.wait_task_finish(vm_updated, vm_result, task_msg, 3600)
        if(rc != 0):
            self.logger.warning('Unable to finish virtual machine DRS migration updating within one hour')
        return rc


    # wait for task to complete
    #
    def wait_task_finish(self, vm_deployed, vm_result, task_msg, timeout):
        while(timeout > 0):
            vm_num = len(vm_deployed.keys())
            count = 0
            self.logger.info( ('-'*15 + "Waiting for %s" + '-'*15) % task_msg )

            for vm in vm_deployed.keys():
                task = vm_deployed[vm]
                info = task.info

                if info.state == vim.TaskInfo.State.success:
                    self.logger.info('%s %s is successfully done' % (task_msg, vm))
                    vm_result[vm] = 1
                    count = count + 1
                elif info.state == vim.TaskInfo.State.running:
                    self.logger.info('%s %s is still running and task is at %s percent' % (task_msg, vm, info.progress))
                elif info.state == vim.TaskInfo.State.queued:
                    self.logger.info('%s %s task is queued' % (task_msg, vm))
                elif info.state == vim.TaskInfo.State.error:
                    if info.error.fault:
                        self.logger.warning('%s %s task has quit with error: %s' % (task_msg, vm, info.error.fault.faultMessage))
                    else:
                        self.logger.warning('%s %s task has quit with cancelation' % (task_msg, vm))
                    count = count + 1

            if(count == vm_num):
                return 0 

            time.sleep(20)
            timeout = timeout - 20

        self.logger.warning("Task %s does not finish within %d seconds" % (task_msg, timeout))
        return 1 


    def _get_task_vm(self, task, task_d):
        task_str = str(task)
        for vm in task_d.keys():
            if( task_str == str(task_d[vm]) ):
                return vm
        return None


    # wait for update task to complete
    #
    def wait_update_task(self, update_tasks, task_msg, timeout):
        content = self.conn_content 
        property_collector = content.propertyCollector
  
        tasks = list(update_tasks.values())
        task_list = [str(task) for task in tasks]

        obj_specs = [vmodl.query.PropertyCollector.ObjectSpec(obj=task) for task in tasks]
        property_spec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task, pathSet=[], all=True)

        filter_spec = vmodl.query.PropertyCollector.FilterSpec()
        filter_spec.objectSet = obj_specs
        filter_spec.propSet = [property_spec]
        pcfilter = property_collector.CreateFilter(filter_spec, True)
 
        task_number = len(task_list)
        task_success = [] 

        try:
            version, state = None, None
            # wait for the task to complete
            while(task_list and timeout > 0):
                self.logger.info( ('-'*15 + "Waiting for virtual machine %s" + '-'*15) % task_msg )

                for vm in task_success:
                    self.logger.info('Virtual machine %s %s succeeds' % (vm, task_msg))

                update = property_collector.WaitForUpdates(version)
                for filter_set in update.filterSet:
                    for obj_set in filter_set.objectSet:
                        task = obj_set.obj
                        for change in obj_set.changeSet:
                            if change.name == 'info':
                                state = change.val.state
                            elif change.name == 'info.state':
                                state = change.val
                            else:
                                continue

                            if not str(task) in task_list:
                                continue

                            vm = self._get_task_vm(task, update_tasks)

                            if state == vim.TaskInfo.State.success:
                                task_list.remove(str(task))  # Remove task from taskList
                                task_success.append(vm) 
                                self.logger.info('Virtual machine %s %s succeeds' % (vm, task_msg)) 
                            elif state == vim.TaskInfo.State.error:
                                task_list.remove(str(task))
                                self.logger.warning('Virtual machine %s %s has quit with error' % (vm, task_msg))
                            else:
                                self.logger.info('Virtual machine %s %s is still running' % (vm, task_msg))

                # Move to next version
                version = update.version

                if( len(task_success) == task_number ):  #all the tasks in task_list are complted, not need to wait
                    break

                time.sleep(20)
                timeout = timeout - 20
        except Exception as exp:
            self.logger.warning('Having problem while waiting for tasks to complete. Exception: %s' % exp)
        finally:
            if pcfilter:
                pcfilter.Destroy()
            return 0 if( len(task_success) == task_number ) else 1 

 
    # update the deployed virtual machine's network
    #
    def update_network(self):
        self.logger.info('Start updating virtual machine network')
        if self.network_vds == False:
            network = self.locate_obj(self.network, [vim.Network])
        else:
            network = self.locate_obj(self.network, [vim.dvs.DistributedVirtualPortgroup])
        if(network == None):
            self.logger.warn('Unable to find network %s from vcenter %s' % (self.network, self.vc_name))
            return 1

        network_updated = {}

        for vm_name in self.vm_list:
            tmp_vm = self.locate_obj(vm_name, [vim.VirtualMachine])
            if tmp_vm == None:
                self.logger.warn('Unable to find virtual machine %s from vcenter %s' % (vm_name, self.vc_name))
                return 1

            device_change = []
            for device in tmp_vm.config.hardware.device:
                found_instance = isinstance(device, vim.vm.device.VirtualEthernetCard)
                if(found_instance == False):
                    continue

                nicspec = vim.vm.device.VirtualDeviceSpec()
                nicspec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
                nicspec.device = device
                nicspec.device.wakeOnLanEnabled = True

                if self.network_vds == False:  # for non VDS network
                    nicspec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
                    nicspec.device.backing.network = network
                    nicspec.device.backing.deviceName = self.network 
                else:
                    dvs_port_connection = vim.dvs.PortConnection()

                    dvs_port_connection.portgroupKey = network.key
                    dvs_port_connection.switchUuid = network.config.distributedVirtualSwitch.uuid
                    nicspec.device.backing = vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
                    nicspec.device.backing.port = dvs_port_connection

                nicspec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
                nicspec.device.connectable.startConnected = True
                nicspec.device.connectable.allowGuestControl = True
                device_change.append(nicspec)
                break

            config_spec = vim.vm.ConfigSpec(deviceChange=device_change) 
            task = tmp_vm.ReconfigVM_Task(config_spec)
            network_updated[vm_name] = task

        task_msg = 'network update to %s' % self.network
        rc = self.wait_update_task(network_updated, task_msg, 1800)
        return rc


    # get the deployed virtual machine's operating system type
    #
    def get_vm_ostype(self):
        for vm_name in self.vm_list:
            tmp_vm = self.locate_obj(vm_name, [vim.VirtualMachine])
            if not tmp_vm:
                self.logger.warn('Unable to find virtual machine %s from vcenter %s' % (vm_name, self.vc_name))
                return 1

            vm_ostype = tmp_vm.summary.config.guestFullName
            if(vm_ostype == None):
                continue
            if(re.search('Windows', vm_ostype, re.M|re.I) != None):
                self.vm_ostype = "Windows"
                return 0
            elif(re.search('Linux', vm_ostype, re.M|re.I) != None):
                self.vm_ostype = "Linux"
                return 0
            elif(re.search('CentOS', vm_ostype, re.M|re.I) != None):
                self.vm_ostype = "Linux"
                return 0

        if(self.vm_ostype == None):
            self.logger.warn('Error: unable to get the deployed virtual machine operating system type')
            return 1


    # set up linux virtual machine's static ip address and DNS server. If user specifies DHCP, vm will be configued using DHCP.
    #
    def setup_linux_ip(self):
        if(self.static_ip == False):
            return 0

        vm_deployed = {}
        vm_result = {}
        task_msg = "Virtual machine static IP setup"
        self.logger.info('Start setting up virtual machine static IP address')
        for i in range(len(self.vm_list)):
            vm_name = self.vm_list[i]
            tmp_vm = self.locate_obj(vm_name, [vim.VirtualMachine])
            if not tmp_vm:
                self.logger.warn('Unable to find virtual machine %s from vcenter %s' % (vm_name, self.vc_name))
                return 1
           
            adaptermap = vim.vm.customization.AdapterMapping()
            adaptermap.adapter = vim.vm.customization.IPSettings()
            if(self.static_ip):
                adaptermap.adapter.ip = vim.vm.customization.FixedIp()
                adaptermap.adapter.ip.ipAddress = self.static_ip_list[i] 
                adaptermap.adapter.subnetMask = self.vm_netmask 
                adaptermap.adapter.gateway = self.vm_gateway
            else:
                adaptermap.adapter.ip = vim.vm.customization.DhcpIpGenerator()

            if(self.vm_dns):
                adaptermap.adapter.dnsServerList = self.vm_dns 

            globalip = vim.vm.customization.GlobalIPSettings()
            if(self.vm_dns):
                globalip.dnsServerList = self.vm_dns 

            ident = vim.vm.customization.LinuxPrep()
            ident.hostName = vim.vm.customization.FixedName()
            ident.hostName.name = vm_name

            customspec = vim.vm.customization.Specification()
            customspec.nicSettingMap = [adaptermap]
            customspec.globalIPSettings = globalip
            customspec.identity = ident

            try:
                task = tmp_vm.Customize(spec=customspec)
                vm_deployed[vm_name]=task
            except Exception as exp:
                self.logger.warning('Catching exception while updating virtual machine %s configuration. Exception details: %s' % (vm_name, exp))
                return 1

        rc = self.wait_task_finish(vm_deployed, vm_result, task_msg, 3600)
        return rc


    # set up windows virtual machine's ip address and DNS server
    #
    def setup_win_ip(self):
        creds = vim.vm.guest.NamePasswordAuthentication( username=self.vm_user, password=self.vm_password )
        content = self.conn_content
        profile_manager = content.guestOperationsManager.processManager

        self.logger.info('Start setting up virtual machine static IP address')
        for i in range(len(self.vm_list)):
            vm_name = self.vm_list[i]
            self.logger.info('Setting up static IP address %s for virtual machine %s' % (self.static_ip_list[i], vm_name))

            tmp_vm = self.locate_obj(vm_name, [vim.VirtualMachine])
            if not tmp_vm:
                self.logger.warn('Unable to find virtual machine %s from vcenter %s' % (vm_name, self.vc_name))
                return 1

            # set up vm ip address
            win_cmd1 = "interface ipv4 set address Ethernet0 static %s %s %s" % (self.static_ip_list[i], self.vm_netmask, self.vm_gateway)
            program_spec1 = vim.vm.guest.ProcessManager.ProgramSpec( programPath="c:\\windows\\system32\\netsh.exe", arguments=win_cmd1)
            tools_status = tmp_vm.guest.toolsStatus
            res = profile_manager.StartProgramInGuest(tmp_vm, creds, program_spec1)
            time.sleep(10)

            # set up vm DNS
            win_cmd2 = "interface ipv4 set dnsserver Ethernet0 static %s primary" % (self.vm_dns)
            program_spec2 = vim.vm.guest.ProcessManager.ProgramSpec( programPath="c:\\windows\\system32\\netsh.exe", arguments=win_cmd2)
            res = profile_manager.StartProgramInGuest(tmp_vm, creds, program_spec2)

        time.sleep(30)
        for i in range(len(self.vm_list)):
            vm_name = self.vm_list[i]
            tmp_vm = self.locate_obj(vm_name, [vim.VirtualMachine])
            if not tmp_vm:
                self.logger.warn('Unable to find virtual machine %s from vcenter %s' % (vm_name, self.vc_name))
                return 1

            # reboot the vm
            program_spec3 = vim.vm.guest.ProcessManager.ProgramSpec( programPath="c:\\windows\\system32\\shutdown.exe", arguments="/r /t 5")
            tools_status = tmp_vm.guest.toolsStatus
            res = profile_manager.StartProgramInGuest(tmp_vm, creds, program_spec3)

            self.logger.info('Done with setting up static IP address for virtual machine %s' % vm_name)

        time.sleep(60) # for all the vms, give one minute to reboot
        self.logger.info('Done with setting up static IP addresses for all the virtual machines')
        return 0


    # update windows virtual machine's hostname
    #
    def update_win_hostname(self):
        self.logger.info("Start updating virtual machine hostname")

        rc = self.wait_vm_up(1800)
        if(rc != 0): return rc

        creds = vim.vm.guest.NamePasswordAuthentication( username=self.vm_user, password=self.vm_password )
        content = self.conn_content
        profile_manager = content.guestOperationsManager.processManager

        for i in range(len(self.vm_list)):
            vm_name = self.vm_list[i]
            tmp_vm = self.locate_obj(vm_name, [vim.VirtualMachine])
            if not tmp_vm:
                self.logger.warn('Unable to find virtual machine %s from vcenter %s' % (vm_name, self.vc_name))
                return 1

            self.logger.info("Updating virtual machine %s hostname" % vm_name)
            # update vm hostname 
            win_cmd = "/C powershell -NonInteractive -Command Rename-Computer -NewName \"%s\" -Restart" % vm_name
            program_spec = vim.vm.guest.ProcessManager.ProgramSpec( programPath="cmd.exe", arguments=win_cmd)
            try:
                tools_status = tmp_vm.guest.toolsStatus
                res = profile_manager.StartProgramInGuest(tmp_vm, creds, program_spec)
            except Exception as exp:
                self.logger.warning('Having problem while updating virtual machine %s hostname. Exception details: %s' % (vm_name, exp))
                return 1

        time.sleep(30)
        rc = self.wait_vm_up(1800)
        self.logger.info("Successfully update virtual machine hostname")
        return rc


    # power up VMs and wait until the vmtools are all available
    #
    def power_up_vm(self):
        vm_processed = {}
        task_msg = 'powering up'
        self.logger.info('Start powering up virtual machine')
        for vm_name in self.vm_list:
            tmp_vm = self.locate_obj(vm_name, [vim.VirtualMachine])
            if not tmp_vm:
                self.logger.warn('Unable to find virtual machine %s from vcenter %s' % (vm_name, self.vc_name))
                return 1
     
            task = tmp_vm.PowerOnVM_Task()
            vm_processed[vm_name]=task
        
        rc = self.wait_vm_up(3600)
        return rc


    # power off virtual machine
    #
    def power_off_vm(self):
        # connect to vCenter first
        rc = self.connect_vc()
        if(rc == 1):
            self.logger.info('Error connecting to vCenter %s' % self.vc_name)
            return rc

        vm_processed = {}
        vm_result = {}
        task_msg = 'Powering off virtual machine'
        self.logger.info('Start powering off virtual machine')

        for vm_name in self.vm_list:
            self.logger.info('Start powering off virtual machine %s' % vm_name)
            tmp_vm = self.locate_obj(vm_name, [vim.VirtualMachine])
            if not tmp_vm:
                self.logger.warn('Unable to find virtual machine %s from vcenter %s' % (vm_name, self.vc_name))
                return 1 
           
            if( tmp_vm.runtime.powerState == 'poweredOn' ):
                task = tmp_vm.PowerOffVM_Task()
                vm_processed[vm_name]=task

        rc = self.wait_task_finish(vm_processed, vm_result, task_msg, 1800)
        return rc


    # waiting for VMs and its installed VMTools to be fully up
    #
    def wait_vm_up(self, timeout_value):
        timeout = int(time.time()) + timeout_value 
        rc = 1
        while( int(time.time()) < timeout ):
            self.logger.info('-'*15 + "Waiting for virtual machine and VMware Tool to be fully up" + '-'*15) 
            booted_vm = 0

            for vm_name in self.vm_list:
                tmp_vm = self.locate_obj(vm_name, [vim.VirtualMachine])
                if not tmp_vm:
                    self.logger.warn('Unable to find virtual machine %s from vcenter %s' % (vm_name, self.vc_name))
                    return 1

                if(tmp_vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn and 
                   tmp_vm.guest.toolsStatus == vim.vm.GuestInfo.ToolsStatus.toolsOk): 
                    self.logger.info('Virtual machine %s and its installed VMware Tool are fully up' % vm_name)
                    booted_vm = booted_vm + 1
                else:
                    self.logger.info('Virtual machine %s and its installed VM Tool are still being booted up' % vm_name)

            if( booted_vm == len(self.vm_list) ):
                rc = 0
                break
            time.sleep(30)
 
        if(rc == 0):
            self.logger.info('Successfully boot up all the specified virtual machines.')
        else:
            self.logger.warning('Unable to fully boot up all the specified virtual machines within %d seconds' % timeout_value)
        return rc 


    # create virtual machine snapshot
    #
    def create_snapshot(self):
        self.logger.info('Start creating virtual machine snapshot')

        #rc = self.wait_vm_up(1800)
        #if(rc != 0): return rc

        vm_updated = {}
        vm_result = {}
        task_msg = 'Virtual machine snapshot creating'

        for vm_name in self.vm_list:
            tmp_vm = self.locate_obj(vm_name, [vim.VirtualMachine])
            if tmp_vm == None:
                self.logger.warn('Unable to find virtual machine %s from vcenter %s' % (vm_name, self.vc_name))
                return 1

            self.logger.info('Creating VM snapshot %s for VM %s' % (self.snapshot_name, vm_name)) 
            task = tmp_vm.CreateSnapshot_Task(name=self.snapshot_name, description=self.snapshot_name, memory=True, quiesce=False)
            vm_updated[vm_name] = task

        rc = self.wait_task_finish(vm_updated, vm_result, task_msg, 3600)
        return rc


    # check if vm with static IP already exists in vCenter
    #
    def check_vm_exist(self):
        if( len(self.static_ip_list) == 0 ):
            return 0

        rc = self.connect_vc()
        if(rc == 1):
            self.logger.info('Error connecting to vCenter %s' % self.vc_name)
            return 1

        vm_exist = []
        searchIndex = self.conn_obj.RetrieveContent().searchIndex
        for tmp_ip in self.static_ip_list:
            vm_found = searchIndex.FindAllByIp(ip=tmp_ip, vmSearch=True)
            if( len(vm_found) == 0 ):
                continue
            elif( len(vm_found) == 1 ):
                vm_exist.append(tmp_ip)
                if( len(self.vm_list) > 0 ):
                    self.vm_list.pop(-1)
                self.deployed_vm.append( vm_found[0].summary.config.name )
                self.logger.info("Virtual machine %s with static IP %s already exists in vCenter %s. Will not create VM with this static IP." % \
                                    (vm_found[0].summary.config.name, tmp_ip, self.vc_name))
            else:
                for item in vm_found:
                    self.logger.warning("Virtual machine %s with static IP %s already existed in vCenter %s" % (item.summary.config.name, tmp_ip, self.vc_name)) 
                self.logger.warning("For static IP %s, it has multiple VMs configured with this IP. Please correct this problem first." % tmp_ip)
                return 1

        # get vms with static IP that do not exist in vCenter
        vm_new = [] 
        vm_new = [ip for ip in self.static_ip_list if ip not in vm_exist]
        if( len(vm_new) == 0 ):
            self.logger.warning("Theare are virtual machines created with the user specified static IP addresses in vCenter %s. Do not deploy any new virtual machines." % \
                                self.vc_name)
            return 2

        self.static_ip_list = copy.deepcopy(vm_new)
        if( len(self.static_ip_list) != len(self.vm_list) ):
            self.logger.warning("The provided static IP address number %d does not equal to the provided VM number %d. Please check the YAML file." % \
                                len(self.static_ip_list), len(self.vm_list))
            return 1
        else:
            return 0 


    # deploy virtual machine
    #
    def deploy_vm(self):
        rc = self.check_vm_exist()
        if(rc == 1):
            return 1 
        elif(rc == 2):  # all the vms with static ips already existed in vCenter, do not create new.
            return 0

        rc = self.build_vm_spec()
        if(rc != 0):
            self.logger.warning('Unable to build virtual machine spacification through vCenter %s' % self.vc_name)
            return rc

        count = 0 
        vm_deployed = {}
        vm_result = {}
        task_msg = 'Virtual machine cloning'

        for vm_name in self.vm_list:
            tmp_vm = self.locate_obj(vm_name, [vim.VirtualMachine])
            if tmp_vm:
                self.logger.warn('Virtual machine %s already exists. Do not clone this virtual machine!' % vm_name)
                continue
    
            task = self.template_obj.Clone(name=vm_name, folder=self.folder_obj, spec=self.vm_spec)
            vm_deployed[vm_name]=task
            self.logger.debug('task id is %d' % id(task))
            count = count + 1
        
            self.logger.info('Start cloning virtual machine %s' % vm_name)
            self.deployed_vm.append(vm_name)  
 
            if(count % 10 == 0):
                self.wait_task_finish(vm_deployed, vm_result, task_msg, 3600)
                vm_deployed = {}

        if( len(vm_deployed.keys()) > 0 ):
            self.wait_task_finish(vm_deployed, vm_result, task_msg, 3600)

        if(self.network != None):
            self.update_network()

        if(self.cluster == None and self.esx != None):
            time.sleep(30)
            rc = self.relocate_vm()
            if(rc != 0): return rc

        for vm_name in vm_result.keys():
            logmessage = 'DEPLOYVM:' + vm_name
            writelog(self.tmplogfile, logmessage, False)
        # done with deploying vm

        rc = self.get_vm_ostype()
        if(rc != 0): return rc

        if(self.vm_ostype == "Linux"):
            rc = self.setup_linux_ip()
            if(rc != 0): return rc

        self.power_up_vm()

        if(self.static_ip and self.vm_ostype == "Windows"):
            time.sleep(30)  # wait 30 seconds until vm's VMTool is fully up
            rc = self.setup_win_ip()
            if(rc != 0): return rc

        if(self.static_ip):
            rc = self.check_static_ip()
            if(rc != 0): return rc

        if(self.hostname_update and self.vm_ostype == "Windows"):
            rc = self.update_win_hostname()
            if(rc != 0): return rc

        if(self.snapshot_name != None):
            rc = self.create_snapshot()
            if(rc != 0): return rc

        if(self.power_on == False):
            rc = self.power_off_vm()
            if(rc != 0): return rc

        deployed_vm_str = ', '.join(self.deployed_vm)
        self.logger.info('='*15 + 'Successfully deploy virtual machines: %s' % deployed_vm_str + '='*15)

        return 0  # All the steps succeed, return 0 here
    # done with deploy_vm


    # delete virtual machine
    #
    def delete_vm(self):
        rc = self.power_off_vm()
        if(rc != 0): return rc

        vm_processed = {}
        vm_result = {}
        task_msg = 'Deleting virtual machine'
        self.logger.info('Start deleting virtual machine')

        for vm_name in self.vm_list:
            self.logger.info('Start deleting virtual machine %s' % vm_name)

            tmp_vm = self.locate_obj(vm_name, [vim.VirtualMachine])
            if not tmp_vm:
                self.logger.warn('Virtual machine %s does not exist.  Do not delete this virtual machine!' % vm_name)
                continue

            task = tmp_vm.Destroy_Task()
            vm_processed[vm_name]=task

        rc = self.wait_task_finish(vm_processed, vm_result, task_msg, 1800)
        return rc


    # get virtual machines' IP addresses from vCenter
    #
    def get_vm_ip(self, vm_list = []):
        ipaddress_list = []

        rc = self.connect_vc()
        if(rc == 1):
            self.logger.info('Error connecting to vCenter %s' % self.vc_name)
            return ipaddress_list

        if( len(vm_list) > 0 ):
            self.vm_list = []
            self.vm_list = copy.deepcopy(vm_list)

        for vm_name in self.vm_list:
            tmp_vm = self.locate_obj(vm_name, [vim.VirtualMachine])
            if not tmp_vm:
                self.logger.warning('Virtual machine %s does not exist. Can not find virtual machine IP address' % vm_name)
                continue
  
            if(hasattr(tmp_vm, "guest") == False):
                self.logger.warning('Virtual machine %s does not have guest attribute created' % vm_name)
                continue

            if(hasattr(tmp_vm.guest, "ipAddress") == False):
                self.logger.warning('Virtual machine %s does not have guest ipAddress attribute created' % vm_name)
                continue
 
            if( (tmp_vm.guest.ipAddress == None) or (len(tmp_vm.guest.ipAddress) == 0) ):
                self.logger.warning('Error getting virtual machine %s IP address' % vm_name)
                continue 
       
            vm = {}
            vm["vm_name"] = vm_name
            vm["vm_ip"] = tmp_vm.guest.ipAddress
            ipaddress_list.append(vm)

        return ipaddress_list 

