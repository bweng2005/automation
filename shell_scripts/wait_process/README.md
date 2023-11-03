## wait_process scripts

### Description:
This BASH script wait_process.sh shows how to wait for multiple processes to complete and get their exit codes accordingly. These scripts have been tested on Bash version 5.0.17 and 5.1.8.

### Components:
- wait_process.sh: This Bash script starts sample_process.sh as the sample processes.  sample_process.sh will run for a random 30 to 60 seconds. While sample_process.sh runs in the background, wait_process.sh can watch these spawned sample_process.sh processes and get their exit codes after these spawned sample_processes.sh processes complete execution. 
- sample_process.py: The Bash script will run for a random 30 to 60 seconds.

User can run this script in this command line:

``` ./wait_process.sh```
