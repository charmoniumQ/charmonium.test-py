#!/bin/bash
# set -e helps me identify failed runs
set -e
doi="$1" # get DOI
test=False

# check if testing arg provided
if [ -n "$2" ]; then
    test=True
fi

# set default CRAN mirror
echo 'local({r <- getOption("repos");
       r["CRAN"] <- "http://cran.us.r-project.org"; 
       options(repos=r)})' >> ~/.Rprofile
# This will cause errors because it prints a literal \n:
#echo '\n' >> ~/.Rprofile

# download dataset
# Also disable and re-enable set -e
set +e
timeout 1h python2 download_dataset.py "$doi"
status=$?
set -e

if [ $status -eq 124 ]; then
     echo "$doi,unknown,download error" >> run_log.csv
else
     # only needed for R 3.2.1
     #ln -s /lib/x86_64-linux-gnu/libreadline.so.7.0 /lib/x86_64-linux-gnu/libreadline.so.6

     # process all R files and collect data

     # add brackets to metrics.txt so that the file is readable with json
     echo "[" >> metrics.txt
     # This lets me use the same image when cleaning and when not cleaning
     if [ -n "${clean_env}" ]; then
     python2 set_environment.py $PWD
     fi

     # execute R files with 3 hour limit
     timeout 5h Rscript exec_r_files.R "$doi"

     # note if 3hr time limit exceeded 
     if [ $? -eq 124 ]; then
          echo "$doi,unknown,time limit exceeded" >> run_log.csv
     fi

     sed -i '$s/,$//' metrics.txt
     echo "]" >> metrics.txt
fi

# send results
# Instead of DyanmoDB, we will save the results in /results
# The caller will pick them up from a volume-mount
mkdir -p /results
for file in run_log_ds.csv run_log.csv metrics.csv run_log_st1.csv run_log_st.csv; do
    if [ -f "${file}" ]; then
        mv "${file}" "/results/${file}"
    fi
done
