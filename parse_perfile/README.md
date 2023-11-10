## parse_perfile script

### Description:
This Python script parse_perfile.py can be used to parse certain performance output files and show the performance run statistics. 

### Components:
- parse_perfile.py: This Python script can parse a performance output file and show the performance test run statistics for different performance test runs.
  - In the performance output file, the beginning of each test run is marked by "&&&& RUNNING". For each individual test run, this Python script can show if the test run PASSED or FAILED.
  - Each test run might contain one or more performance test cycles. In the performance output file, the performance test cycle is marked by "&&&& PERF" as the beginning and the end of the performance test cycle. This Python script can parse each performance test cycle and show the test results to user.
  - Within each performance test cycle, since it contains multiple latency entries, this script will find the lowest latency entry and show the latency to user. When calculating latency, the script divides the latency time by the byte size. Only the lowest latency entry will be shown. For example, the performance output file has the following latency entry. The script will calculate this entry's latency by dividing 3.95264 by 256. The result is 0.01544 microsecond(us).

    "shmem_p_latency___None___size__256___latency 3.95264 -us"

  - Within each performance test cycle, since it contains multiple throughput entries, this script will find the highest throughput entry and show the throughput to user. When calculating the throughput, the script will NOT divide the throughtput by the byte size as that does not make sense. For example, the performance output file has the following throughput entry. The script will directly use the throughput as 1.862648 GB/sec. It will not divide 1.862648 by the byte size 8192. 
    
    "shmem_p_bw___None___size__8192___BW 1.862648 +GB/sec"
    
  - Within each performance test cycle, if it contains either "uni" or "bidi" throughput entries, the script will show the highest individual "uni" or "bidi" throughput respectively.
  - Within each performance test cycle, if it contains either "Thread", "Warp" or "Block" latency entries, the script will show the lowest individual "Thread", "Warp" or "Block" latency respectively.

User can run this script in this command line:

``` ./parse_perfile.py -f perf_run_output_file```
