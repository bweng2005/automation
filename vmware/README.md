## VMWare automation scripts

### Description:
Warning: this code is provided on a best effort basis and is not in any way officially supported by VMware. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

These VMware python automation scripts allow user to deploy or delete VMware virtual machines through vCenter. User needs to specify a yaml file to provide the vCenter information. In the yaml file, user needs to provide either the ESXi cluster or the ESXi server information in which the new virtual machines will be deployed. Please use the provided "vm_deploy.yaml" file as a template and add your detailed vCenter and ESXi server information.

### Components:
vmwarevms.py

vm_operation.py

autoutil.py

vm_deploy.yaml

User can run this script in this command line: "./vm_operation.py -fy vm_deploy.yaml -ys esx_1 -l INFO -o vm_operation-1.log"

### Parameters:
yamlfile: User specified yaml file

yamlsection: User specified ESXi section to deploy the virtual machines in the yaml file

loglevel: Log file level. The default log file level is "INFO".

outlogfile: Output log file name. The default output log file name is "vm_oper_$date.log".   
