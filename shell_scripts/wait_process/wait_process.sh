#!/usr/bin/bash

bash51_ver="5.1"
bash51=false

if [[ "$BASH_VERSION" == *"$bash51_ver"* ]]; then
    bash51=true
fi

declare -A pid_array

# Wait for processes to complete for BASH whose version is lower than 5.1
#
get_process_exit_code() {
    for pid in ${pid_array[@]}
    do
        cmd="wait $pid"
        echo "Waiting for process ID $pid"
        eval "$cmd"
        exit_code=$?
        echo "PID $pid exits with exit code as $exit_code" 
    done
}

# Wait for processes to complete for Bash whose version is 5.1 or above. For Bash "wait" command,
# the option "-p" is only available on Bash version 5.1 or above.
#
get_bash51_process_exit_code() {
    while [ ${#pid_array[@]} -gt 0 ]
    do
        cmd="wait -n -p PID ${!pid_array[@]}"
        echo "Waiting for process IDs ${!pid_array[@]}"   
 
        eval "$cmd"
        exit_code=$?

        echo "PID $PID exits with exit code as $exit_code"
        unset pid_array[$PID]
        #sleep 1
    done
}

# Start user processes here. This is to demonstrate how function get_bash51_process_exit_code or get_process_exit_code can be
# used to wait for processes to complete and get their exit codes accordingly
#
for count in {1..5}
do
    ./sample_process.sh >> /dev/null &
    PID=$!
    pid_array[$PID]=$PID
done

echo "Started ${#pid_array[@]} process. Their process IDs are ${!pid_array[@]}"

if [ "$bash51" = true ]
then
    get_bash51_process_exit_code
else
    get_process_exit_code
fi
