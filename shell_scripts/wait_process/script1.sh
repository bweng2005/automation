#!/usr/bin/bash

random_num=$(shuf -i 30-60 -n 1)
echo "Process ID is $$. Sleep for $random_num seconds"
sleep $random_num

exit $random_num
