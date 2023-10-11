## VMWare automation scripts

### Description:
Warning: this code is provided on a best effort basis and is not in any way officially supported by VMware. 

These VMware python automation scripts allow user to deploy or delete VMware virtual machines through vCenter. User needs to specify a yaml file to provide the vCenter information. In the yaml file, user needs to provide either the ESXi cluster or the ESXi server information in which the new virtual machines will be deployed. Please use the provided "vm_deploy.yaml" file as a template and add your detailed vCenter and ESXi server information.

### Components:
- vmwarevms.py: The main Python script that handles VMWare vCenter virtual machine deployment or deletion
- vm_operation.py: The Python script that shows how to use the exported modules from vmwarevms.py
- autoutil.py: A utility Python script
- vm_deploy.yaml: The yaml file that user needs to update to provide the vCenter and the ESXi server information. User can specify the details of the deployed virtual machines.

User can run this script in this command line:

``` ./vm_operation.py -yf vm_deploy.yaml -ys esx_1 -l INFO -o vm_operation-1.log```

or 

``` ./vm_operation.py -yf vm_deploy.yaml -ys esx_2 -l INFO -o vm_operation-1.log```

### Parameters:
- -yf, --yamlfile: User specified yaml file
- -ys, --yamlsection: User specified ESXi section to deploy the virtual machines in the yaml file
- -l, --loglevel: Log file level. The default log file level is "INFO".
- -o, --outlogfile: Output log file name. The default output log file name is "vm_oper_$date.log".   
