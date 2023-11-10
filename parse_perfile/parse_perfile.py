#!/usr/bin/env python3

import re
import sys
import argparse

# extract performance latency from a line like this:
# "shmem_p_latency___None___size__256___latency 3.95264 -us"
#
def extract_latency(line_list):
    perf_name = line_list[0]
    
    # perf_name is in this format: "shmem_p_latency___None___size__256___latency"
    pattern = r'size(_+)(\d+)(_+)latency'
    res = re.search(pattern, perf_name)
    if(res is None):
        return None
    size = float(res.group(2)) # get the byte size for example 4,8,16...etc.

    # run time is in this format: "3.95264 -us"
    val = float(line_list[1])
    val = float(val/size)  # divide the run time by the byte size
    val = round(val, 6)

    return val

# For each performance section that starts and ends with "&&&& PERF", get this section's
# performance details. This includes either latency or throughput detail. For throughput, this
# function can differentiate between uni/bidi. For latency, this function can differentiate 
# among thread/warp/block.
def get_perf_details(perf_section):
    uni, bidi = {}, {} 
    thread, warp, block = {}, {}, {}
    latency, throughput = {}, {}

    for line in perf_section:
        # a perfmance output line is in this format: "shmem_put_latency___Thread___size__256___latency 6.31296 -us"

        line = line.strip()
        pattern = r'&&&& PERF(\s*)'
        res = re.search(pattern, line)
        if(res is not None):
            line = re.sub(pattern, "", line)
        # the above will remove the "&&&& PERF " from this performance output line
        # &&&& PERF shmem_put_latency___Thread___size__4___latency 4.20352 -us

        #print(line)
        tmp_line = line.split()
        if( len(tmp_line)!=3 ): # every performance line should have three columns: perf_run_detail, run_time and unit
            continue

        perf_name = tmp_line[0]
        unit = tmp_line[2]

        # for uni throughput entry, perf_name is in this format: "shmem_put_bw_uni___None___size__1024___BW"
        if("_uni___" in perf_name):            
            val = float(tmp_line[1])
            if(len(uni) == 0):
                uni["perf_name"] = perf_name
                uni["val"] = val
            elif(val > uni["val"]):
                uni["perf_name"] = perf_name
                uni["val"] = val
            continue

        # for bidi throughput entry, perf_name is in this format: "shmem_put_bw_bidi___None___size__1024___BW"
        if("_bidi___" in perf_name):
            val = float(tmp_line[1])
            if(len(bidi) ==0):
                bidi["perf_name"] = perf_name
                bidi["val"] = val
            elif(val > bidi["val"]):
                bidi["perf_name"] = perf_name
                bidi["val"] = val
            continue

        # for Thread latency entry, perf_name is in this format: "shmem_put_latency___Thread___size__256___latency"
        pattern = r"(\S+)Thread(_+)size(\S+)latency"
        res = re.search(pattern, perf_name)
        if(res is not None):            
            val = extract_latency(tmp_line)
            if(val is None):
                continue   
            # did not get a valid latency

            if(len(thread) == 0):
                thread["perf_name"] = perf_name
                thread["val"] = val
            elif(val < thread["val"]):
                thread["perf_name"] = perf_name
                thread["val"] = val
            continue

        # for Warp latency entry, perf_name is in this format: "shmem_put_latency___Warp___size__4___latency"
        pattern = r"(\S+)Warp(_+)size(\S+)latency"
        res = re.search(pattern, perf_name)
        if(res is not None):            
            val = extract_latency(tmp_line)
            if(val is None):
                continue   
            # did not get a valid latency

            if(len(warp) == 0):
                warp["perf_name"] = perf_name
                warp["val"] = val
            elif(val < warp["val"]):
                warp["perf_name"] = perf_name
                warp["val"] = val
            continue
        
        # for Block latency entry, perf_name is in this format: "shmem_put_latency___Block___size__4___latency"
        pattern = r"(\S+)Block(_+)size(\S+)latency"
        res = re.search(pattern, perf_name)
        if(res is not None):            
            val = extract_latency(tmp_line)
            if(val is None):
                continue   
            # did not get a valid latency

            if(len(block) == 0):
                block["perf_name"] = perf_name
                block["val"] = val
            elif(val < block["val"] ):
                block["perf_name"] = perf_name
                block["val"] = val
            continue

        # for any other latency performance entry, it is in this format: "shmem_p_latency___None___size__4___latency"
        pattern = r"(_+)latency$"
        res = re.search(pattern, perf_name)
        if(res is not None):            
            val = extract_latency(tmp_line)
            if(val is None):
                continue   
            # did not get a valid latency

            if(len(latency) == 0):
                latency["perf_name"] = perf_name
                latency["val"] = val
            elif(val < latency["val"]):
                latency["perf_name"] = perf_name
                latency["val"] = val
            continue

        # for any other throughput performance entry, it is in this format: "shmem_p_bw___None___size__1024___BW 0.232831 +GB/sec"
        pattern = r"GB/sec$"
        res = re.search(pattern, unit)
        if(res is not None):
            val = float(tmp_line[1])
            if(len(throughput) ==0):
                throughput["perf_name"] = perf_name
                throughput["val"] = val
            elif(val > throughput["val"]):
                throughput["perf_name"] = perf_name
                throughput["val"] = val
            continue

    unit = re.sub(r"^(\+)|(\-)", "", unit)  # for unit like "+GB/sec" or "-us", remove the leading "+" or "-"
    column_width = 50
    if(len(latency) > 0):
        outline = "\t\t latency test best performance:".ljust(column_width) + latency["perf_name"].ljust(column_width) + "\n"
        outline = outline + "\t\t latency test result:".ljust(column_width) + ("{:.6f} {}".format(latency["val"], unit)).ljust(column_width)
        print(outline)

    if(len(throughput) > 0):
        outline = "\t\t throughput test best performance:".ljust(column_width) + throughput["perf_name"].ljust(column_width) + "\n"
        outline = outline + "\t\t throughput test result:".ljust(column_width) + ("{:.6f} {}".format(throughput["val"], unit)).ljust(column_width)
        print(outline)

    if(len(thread) > 0):
        outline = "\t\t thread latency test best performance:".ljust(column_width) + thread["perf_name"].ljust(column_width) + "\n"
        outline = outline + "\t\t thread latency test result:".ljust(column_width) + ("{:.6f} {}".format(thread["val"], unit)).ljust(column_width)
        print(outline)

    if(len(warp) > 0):
        outline = "\t\t warp latency test best performance:".ljust(column_width) + warp["perf_name"].ljust(column_width) + "\n"
        outline = outline + "\t\t warp latency test result:".ljust(column_width) + ("{:.6f} {}".format(warp["val"], unit)).ljust(column_width)
        print(outline)

    if(len(block) > 0):
        outline = "\t\t block latency test best performance:".ljust(column_width) + block["perf_name"].ljust(column_width) + "\n"
        outline = outline + "\t\t block latency test result:".ljust(column_width) + ("{:.6f} {}".format(block["val"], unit)).ljust(column_width)
        print(outline)

    if(len(uni) > 0):
        outline = "\t\t uni throughput test best performance:".ljust(column_width) + uni["perf_name"].ljust(column_width) + "\n"
        outline = outline + "\t\t uni throughput test result:".ljust(column_width) + ("{:.6f} {}".format(uni["val"], unit)).ljust(column_width)
        print(outline)

    if(len(bidi) > 0):
        outline = "\t\t bidi throughput test best performance:".ljust(column_width) + bidi["perf_name"].ljust(column_width) + "\n"
        outline = outline + "\t\t bidi throughput test result:".ljust(column_width) + ("{:.6f} {}".format(bidi["val"], unit)).ljust(column_width)
        print(outline)

    print("-"*120)
    
# for each test, get its test performance results
#
def get_test_result(test_name, test_section):
    test_result = "Not found"
    
    for i in range(1, len(test_section)):
        line = test_section[i].strip()
        pattern = r'^&&&&(\s+)(\S+)(\s+)%s' % test_name
            # search for string like "&&&& PASSED device/pt-to-pt/shmem_p_latency -n 2 -npernode 2"
        
        res = re.search(pattern, line)
        if(res is not None):
            result = res.group(2)
            test_result = result

    print("Test Name: \t %s" % test_name)
    print("Test Result: \t %s" % test_result)
    # get the test result(PASSED or FAILED) for this particular test_name

    start_index, end_index = None, None
    for i in range(len(test_section)):
        line = test_section[i].strip()
        pattern = r'^&&&& PERF'
        res = re.search(pattern, line)
        if(res is not None):
            if(start_index is None):
                start_index = i
            else:
                end_index = i
                perf_section = test_section[start_index:end_index+1]

                get_perf_details(perf_section)

                start_index = None       

# get test performance results from the user provided file
#
def get_test_performance(input_file):
    try:
        with open(input_file) as fh:
            file_lines = fh.readlines()
    except FileNotFoundError as e:
        print("File not found:", str(e))
        sys.exit(1)
    except IOError as e:
        print("An IOError occurred:", str(e))
        sys.exit(1)
    except Exception as e:
        print("An exception occurred:", str(e))
        sys.exit(1)

    start_index = None
    prev_test_name = None

    for i in range(len(file_lines)):
        pattern = r'^&&&& RUNNING(\s+)(\S+)'
            # search for string like "&&&& RUNNING device/pt-to-pt/shmem_p_latency -n 2 -npernode 2"
        line = file_lines[i].strip()
        res = re.search(pattern, line)
        if(res is not None):
            test_name = res.group(2)
            if(start_index is None):
                start_index = i                
            else:
                end_index = i
                test_section = file_lines[start_index:end_index]
                # get the test_section that starts as "&&&& RUNNING..." and ends as "&&&& PASSED..." 

                get_test_result(prev_test_name, test_section)      

                start_index = end_index
            prev_test_name = test_name

def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--perfile', required=True, help='Performance results file', dest='perfile', type=str)
    args = parser.parse_args()

    perfile = args.perfile
    print("Parsing performance results file '%s' to get performance run details" % perfile)

    get_test_performance(perfile)
    return (0)

if __name__ == "__main__":
    rc = main(sys.argv[1:])
    sys.exit(rc)
