# Email

Hello Ana Trisovic,

We met a while back at eScience '22 in Salt Lake City.

I've been working on evaluating the state of crash-free reproduction of
computational experiments in practice. In other words, I go to some registry of
computational experiments (e.g., Snakemake Workflow Catalog, nf-core), I run all
of the scripts there, and I count how many work [1]. I want to make an
extensible software platform that can do this kind of evaluation for an
arbitrary registry (e.g. WorkflowHub, dockstore, etc.) and arbitrary language
(e.g. Snakemake, Nextflow, Python, etc.) and compare the results in a consistent
way.

This brought me to your work "A large-scale study on research code quality and
execution". I want to put add Harvard Dataverse as a registry and R as a
language that my platform supports. As such, I want to reproduce the results of
your experiment in this publication.

While reproducing your work, I came across these problems:

A1: Dataverse allows the user to upload multiple versions of packages (data and
code) to its website. For example, this package has two versions with slightly
different R codes [3]. It seems the reproducibility package you published always
calls for the latest one [2]. Do you know what date your experiments were run?
If you know that, I can try to use "the latest version before this date" to get
a consistent version of the dataverse packages as the one used in your
experiment.

A2: There are some discrepancies between the sets of DOIs reported in the
datasets here [4]. For example, there are 2 DOIs in run_log_r32_env_download.csv
not in run_log_r36_env_download.csv and 282 dois in the latter but not the
former. There are 61 DOIs in run_log_r32_env.csv not in run_log_r32_no_env.csv,
and 177 DOIs in the latter but not the former. There are 304 DOIs in
run_log_r32_env.csv not in run_log_r32_env_download.csv and 249 DOIs in the
latter but not the former. These discrepancies can be found with [following
code][5]. It seems they are all a subset of the total DOI set [5]. Should there
be the same number of DOIs regardless of R version, regardless of env cleaning,
regardless of if we look at download status or run status?

A3: I was unable to build the Dockerfile you used because the Conda environment
for R 3.2 is no longer solvable [6]. I think this is because the Conda
repositories can delete packages whenever they want. Indeed, the oldest
`r-base-*` in Conda's R repository is 3.3.1 [7]. Can you confirm that the
Dockerfile no longer builds on your machine or is this just on my machine (also
see B1)?

There are other problems, but I was able to workaround these. Please comment if
you think my workaround is not valid.

B1: I was unable to build the Dockerfile you used because `RUN apt-get update`
[fails][8]. This probably has to do with the fact that `continuumio/miniconda`
uses Debian 10.x (Buster) as a baseimage, but Buster is [no longer supported by
Debian][9] (superseded by newer releases). I was able to work around this by
changing the command to `RUN apt-get update
--allow-releaseinfo-change`. However, future Dockerfiles should use
`continuumio/miniconda3` to get the latest miniconda and Debian release.

For assessing reproducibility, I will try to use a method as close as possible
to your work. But there are some things I will change to improve the accuracy
for future work on the platform. Please let me know if you have any questions,
comments or especially objections to the validity with any of these changes.

C1: I found a bug with the way that Dataverse displays MD5 hashes to the
user. Sometimes they report `hash(transform(file))`, but only supply `file`,
when you attempt to download it [10]. This would get recorded in your script as
a "failed download", but it should actually be a correct download. Until this
bug is fixed, I'm going to use the length as a checksum. This is still
susceptible to some errors, but they are quite rare; the download method goes
over HTTPS over TLS over TCP, which already has a checksum [11], so I think a
byte-substitution error is quite rare. The only other kind of downloda error I
am aware of is in cases like this one [12] where the dataset's file access is
restricted. For these, I will avoid even attempting to download the file if they
are restricted access. There is precedent for using file-length, as rsync does
this by default.

C2: The source code notes that we must try `Rscript file.R` in addition to
`source("file.R")` because "source cannot parse R file and sees syntax errors
even when there are none" [13]. I was wondering about the other way around. Does
`Rscript file.R` work for a superset of `source("file.R")`? If this is the case,
why even trying `source("file.R")` in the first place if `Rscript file.R` will
work?  In that case, one wouldn't need to clear the `external_vars`.

Thank you for reading this lengthy email. I look forward to getting your
feedback on these problems. I hope I can involve you in building a platform for
automatically evaluating reproducibility.

Sincerely, Samuel Grayson https://samgrayson.me/

[1]: A draft of my work on reproducing Snakemake and nf-core repositories 
https://github.com/charmoniumQ/wf-reg-test/blob/main/docs/reports/Understanding_the_results_of_automatic_reproduction_of_workflows_in_nf_core_and_Snakemake_Workflow_Catalog.pdf

[2]: The site where your experiment calls for the "latest" version, which can change over time 
https://github.com/atrisovic/dataverse-r-study/blob/master/docker/download_dataset.py#L13

[3]: An example of a dataverse dataset with multiple versions
https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/U3QJQZ&version=2.0

[4]: Data files that contain discrepancies
https://github.com/atrisovic/dataverse-r-study/tree/master/analysis/data

[5]: Code to detect discrepancies in data files
```
import requests, csv
url_prefix = "https://raw.githubusercontent.com/atrisovic/dataverse-r-study/master/analysis/data/"
all_dois = requests.get("https://raw.githubusercontent.com/atrisovic/dataverse-r-study/master/get-dois/dataset_dois.txt").text.strip().split("\n")
def get_dois(data_file):
    reader = csv.reader(requests.get(url_prefix + data_file).text.split("\n"), delimiter="\t")
    return set(row[0] for row in reader if len(row) > 1)
dois32 = get_dois("run_log_r32_env_download.csv")
dois36 = get_dois("run_log_r36_env_download.csv")
print(len(dois32 - dois36), "dois in r32 but not in r36")
print(len(dois36 - dois32), "dois in r36 but not in r32")
print(len(dois32 - all_dois), "dois in r32 but not in all_dois")
print(len(dois36 - all_dois), "dois in r36 but not in all_dois")
# 2 dois in r32 but not in r36
# 282 dois in r36 but not in r32
# 0 dois in r32 but not in all dois
# 0 dois in r36 but not in all dois
# remove "len" to see what the actual DOIs are that are in one but not the other.
```

[6]: Conda can't install r=3.2.1 anymore
```
 > [12/23] RUN conda create -y --name r_3.2.1 -c conda-forge r=3.2.1 r-essentials:
#0 4.067 Collecting package metadata (current_repodata.json): ...working... done
#0 90.76 Solving environment: ...working... failed with repodata from current_repodata.json, will retry with next repodata source.
#0 90.76 Collecting package metadata (repodata.json): ...working... done
#0 401.1 Solving environment: ...working... failed
#0 401.1
#0 401.1 PackagesNotFoundError: The following packages are not available from current channels:
#0 401.1
#0 401.1   - r=3.2.1
#0 401.1
#0 401.1 Current channels:
#0 401.1
#0 401.1   - https://conda.anaconda.org/conda-forge/linux-64
#0 401.1   - https://conda.anaconda.org/conda-forge/noarch
#0 401.1   - https://repo.anaconda.com/pkgs/main/linux-64
#0 401.1   - https://repo.anaconda.com/pkgs/main/noarch
#0 401.1   - https://repo.anaconda.com/pkgs/r/linux-64
#0 401.1   - https://repo.anaconda.com/pkgs/r/noarch
#0 401.1
#0 401.1 To search for alternate channels that may provide the conda package you're
#0 401.1 looking for, navigate to
#0 401.1
#0 401.1     https://anaconda.org
#0 401.1
#0 401.1 and use the search bar at the top of the page.
#0 401.1
#0 401.1
------
Dockerfile:17
--------------------
  15 |     
  16 |     RUN conda init bash
  17 | >>> RUN conda create -y --name r_3.2.1 -c conda-forge r=3.2.1 r-essentials
  18 |     RUN conda create -y --name r_3.6.0 -c r r=3.6.0 r-essentials
  19 |     RUN conda create -y -n r_4.0.1 -c conda-forge r-base=4.0.1 r-essentials
--------------------
ERROR: failed to solve: process "/bin/sh -c conda create -y --name r_3.2.1 -c conda-forge r=3.2.1 r-essentials" did not complete successfully: exit code: 1
```

[7]: Conda's R repository (earliest `r-base-*` is 3.3.1)
https://repo.anaconda.com/pkgs/r/linux-64/

[8]: apt-get update in Dockerfile fails, because Buster is no longer supported.
```
#0 0.665 Get:1 http://deb.debian.org/debian buster InRelease [122 kB]              
#0 0.685 Get:2 http://security.debian.org/debian-security buster/updates InRelease [34.8 kB]                                                                          
#0 0.787 Get:3 http://deb.debian.org/debian buster-updates InRelease [56.6 kB]     
#0 1.109 Reading package lists...
#0 2.122 E: Repository 'http://security.debian.org/debian-security buster/updates InRelease' changed its 'Suite' value from 'stable' to 'oldstable'
#0 2.122 E: Repository 'http://deb.debian.org/debian buster InRelease' changed its 'Suite' value from 'stable' to 'oldstable'
#0 2.123 E: Repository 'http://deb.debian.org/debian buster-updates InRelease' changed its 'Suite' value from 'stable-updates' to 'oldstable-updates'
------
Dockerfile:3
--------------------
   1 |     FROM continuumio/miniconda
   2 |     
   3 | >>> RUN apt-get update
   4 |     RUN apt-get install -y software-properties-common
   5 |     
--------------------
ERROR: failed to solve: process "/bin/sh -c apt-get update" did not complete successfully: exit code: 100
```

[9]: Debian announcement that Buster is now end-of-life
https://www.debian.org/News/2022/20220910

[10]: Bug in dataverse regarding incorrect md5 hash
https://github.com/IQSS/dataverse/issues/9501

[11]: TCP protocol already has a checksum
https://en.wikipedia.org/wiki/Transmission_Control_Protocol#Checksum_computation

[12]: Example of a dataset with restricted access
https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/YQ2HFG&version=1.0

[13]: Note in the source
https://github.com/atrisovic/dataverse-r-study/blob/master/docker/exec_r_files.R#L62

# Missing code

- No code to invoke the docker container on each DOI remotely.
- No code to automatically vary the experimental conditions.
  - For example, `docker/save_result_in_dynamo.py` hardcodes one particular experimental condition..

# Code improvements

- Original code mixes Python2.7 and Python3.5 inside the container. Both of these are old, and there is no reason to use two different versions in the same container. In particular, `reticulate` will drop support for Python 2.7 at some point in the future, and the docker container calls `install.packages("reticulate")`, which always pulls down the latest package.
- No dependency on AWS Dynamo or AWS Batch. Instead we use universal_pathlib for storage and Dask for compute. Works locally or in the cloud.
- Uncouple downloading from running and analysis.
- Download once, do N analyses (including run with M versions of R).
- Record version of dataset when downloading.
- Use pyDataverse instead of JSON, Python, and curl.
- Use parallel download.
- Use AST instead of string search to get readability metrics.
  - `"<-function("` to count functions could be inaccurate when `<- function(` is written.
  - `"#" in line` could be inaccurate when `string <- "pound # sign"` is in code.
  - `"test" in line` could be inaccurate.
- Use Nix to build small, reproducible Docker images.
  - https://lazamar.co.uk/nix-versions/?channel=nixpkgs-unstable&package=r
  - Solves will be more long-lasted.
- Code requests "originalFormat", but the md5 hash is for the new format. Therefore, the code will incorrectly say that an md5 mismatch occurs, when really the code requested a different format.
- Use originalFilename instead of guessing the file extension.
```
import requests, tqdm
dois = requests.get("https://raw.githubusercontent.com/atrisovic/dataverse-r-study/master/get-dois/dataset_dois.txt").text.strip().split("\n")
for doi in tqdm.tqdm(dois):
    doi_obj = requests.get(f"http://dataverse.harvard.edu/api/datasets/:persistentId/versions/:latest?persistentId={doi}").json()
    for file_obj in doi_obj["data"]["files"]:
        if "originalFormat" in file_obj:
            print(doi, file_obj["label"])
            break
    else:
        continue
    break
  ```
- Code does not avoid downloading when file access is restricted, but these should fail hash validation and get marked as "failed to download".
- Use `Rscript r_file`rather than `source(r_file)`.
- Installing packages should be baked into the Docker image, not done after instantiation.
- Code should measure resources used (wall time, compute time, RAM, and disk).
- R's `install.packages` installs the latest version of code.

# Email update

Hello Ana Trisovic,

There appear to be new issues.

B3: The line `echo '\n' >> ~/.Rprofile` [14] writes a literal `\n` to the fourth line of `~/.Rprofile`, rather than a newline, which causes R to complain when running any script. See this debugging session [15].

Removing that line [14] makes the problem go away, but it invites the question, is there some difference between the Docker image used in the experiment and the `Dockerfile` in the repository, or perhaps in the execution environment? Can you replicate this problem?

B4: One particular Dataverse R script [16] contains `rm(list=ls())`, which gets `source(..)`ed by `exec_r_files.R`. Note that `rm(...)` and `ls(...)` remove or list variables in the R's global namespace. Then `exec_r_files.R` will fail because it cannot find its own variables (transcript of failure [17]). The script only writes one execution result to `run_log.csv`, where there are 2 R scripts to execute. I can fix this by moving the block labeled `restore local variables` [20] up just before calling `get_readability`.

Interestingly the 4.0 _does_ have 2 execution results [18], but the 3.6 only has 1 [19] so this problem must be absent on the docker container used in 4.0 but present in 3.6. Are you sure that the R 3.6 and R 4.0 results use the _exact same_ conditions except changing the `r_ver` while building the `Dockerfile` and changing the path to `Rscript` in `execute_files.py`?

B5: R 3.6.0 cannot install `reticulate` because it is missing `RcppTOML` [21]. `docker build . --build-arg r_3.6.0 --tag r_3.6.0` will work, but `reticulate` is installed at runtime, so `docker run r_3.6.0 ...` will not [21]. Note that 4.0.1 will build and run, so I know the invocation is correct.

`cannot install reticulate, missing RcppTOML`

To fix this, I install `r-reticulate` and `r-r.utils` with Conda at build-time. However, when I do this, Conda runs out of memory trying to solve the package environment, so I also removed the `conda-forge` channel. The packageset can be solved without bringing in the extra packages in `conda-forge`.

B6: `exec_r_files.R` sets Python to 2.7 before running `execute_files.py`, but `execute_files.py` uses 3.x features, such as `from subprocess import TimeoutError`. Changing this to be 3.5 makes the script work.

After resolving these issues and the ones in the previous email, I am able to build and run the Docker container. Of the first ten DOIs, our results seem to match completely.

[14]: This line writes literal '\n' (not a newline) to `~/.Rprofile`
https://github.com/atrisovic/dataverse-r-study/blob/master/docker/run_analysis.sh#L14

[15]:
```
$ docker run -it --rm --entrypoint /bin/bash atrisovic/aws-image
(r_3.6.0) root@e006afe47dd7:/usr/workdir# ./run_analysis.sh doi:10.7910/DVN/U3QJQZ
Requesting file metadata from  http://dataverse.harvard.edu/api/datasets/:persistentId/versions/:latest?persistentId=doi:10.7910/DVN/U3QJQZ
downloading from http://dataverse.harvard.edu/api//access/datafile/3651317
... more of the same...
Error: 4:1: unexpected input
4: \
    ^
Execution halted
[{'status': 'ok', 'doi': 'doi:10.7910/DVN/U3QJQZ', 'fileid': 'all'}]

$ Rscript -e 'print(0)'
Error: 4:1: unexpected input
4: \
    ^
Execution halted

$ cat ~/.Rprofile
local({r <- getOption("repos");
       r["CRAN"] <- "http://cran.us.r-project.org"; 
       options(repos=r)})
\n
```


[16]: Dataverse R script with `rm`
https://dataverse.harvard.edu/file.xhtml?persistentId=doi:10.7910/DVN/XY2TUK/C7YFCJ&version=1.0

[17]: Example transcript of failure due to a called script running `rm(...)`
```
$ ./run_analysis.sh doi:10.7910/DVN/XY2TUK
Making 'packages.html' ... done
[1] "BasSchub_ISQ_Shocks_ClusterRobust.R" "BasSchub_ISQ_Shocks_Figures.R"
[1] "Executing:  BasSchub_ISQ_Shocks_ClusterRobust.R"
[1] "Executing:  BasSchub_ISQ_Shocks_Figures.R"
Error in get_readability_metrics(arg_temp, filename = r_file) : 
  object 'r_file' not found
Calls: get_readability_metrics -> py_resolve_dots
Execution halted
```

[18]: 2 entries for `doi:10.7910/DVN/XY2TUK` in R 4.0 data https://github.com/atrisovic/dataverse-r-study/blob/master/analysis/data/run_log_r40_no_env.csv#L5259

[19]: 1 entry   for `doi:10.7910/DVN/XY2TUK` in R 3.6 data https://github.com/atrisovic/dataverse-r-study/blob/master/analysis/data/run_log_r36_no_env.csv#L3161

[20]: Restore local variables block https://github.com/atrisovic/dataverse-r-study/blob/master/docker/exec_r_files.R#L42

[21]: `reticulate` fails to install for 
```
$ docker build . --build-arg r_ver=r_3.6.0  --tag r-runner:3.6.0
$ docker run -it --rm -e DOI="doi:10.7910/DVN/U3QJQZ" r-runner:3.6.0
... output trimmed ...
* installing *source* package ‘RcppTOML’ ...
** package ‘RcppTOML’ successfully unpacked and MD5 sums checked
** using staged installation
** libs
x86_64-conda_cos6-linux-gnu-c++ -std=gnu++17 -I"/opt/conda/envs/r_3.6.0/lib/R/include" -DNDEBUG -I../inst/include -DTOML_ENABLE_FLOAT16=0 -I"/opt/conda/envs/r_3.6.0/lib/R/library/Rcpp/include" -DNDEBUG -D_FORTIFY_SOURCE=2 -O2 -isystem /opt/conda/envs/r_3.6.0/include -I/opt/conda/envs/r_3.6.0/include -Wl,-rpath-link,/opt/conda/envs/r_3.6.0/lib  -fpic  -fvisibility-inlines-hidden  -fmessage-length=0 -march=nocona -mtune=haswell -ftree-vectorize -fPIC -fstack-protector-strong -fno-plt -O2 -ffunction-sections -pipe -isystem /opt/conda/envs/r_3.6.0/include -fdebug-prefix-map=/tmp/build/80754af9/r-base_1589917437985/work=/usr/local/src/conda/r-base-3.6.1 -fdebug-prefix-map=/opt/conda/envs/r_3.6.0=/usr/local/src/conda-prefix  -c RcppExports.cpp -o RcppExports.o
x86_64-conda_cos6-linux-gnu-c++ -std=gnu++17 -I"/opt/conda/envs/r_3.6.0/lib/R/include" -DNDEBUG -I../inst/include -DTOML_ENABLE_FLOAT16=0 -I"/opt/conda/envs/r_3.6.0/lib/R/library/Rcpp/include" -DNDEBUG -D_FORTIFY_SOURCE=2 -O2 -isystem /opt/conda/envs/r_3.6.0/include -I/opt/conda/envs/r_3.6.0/include -Wl,-rpath-link,/opt/conda/envs/r_3.6.0/lib  -fpic  -fvisibility-inlines-hidden  -fmessage-length=0 -march=nocona -mtune=haswell -ftree-vectorize -fPIC -fstack-protector-strong -fno-plt -O2 -ffunction-sections -pipe -isystem /opt/conda/envs/r_3.6.0/include -fdebug-prefix-map=/tmp/build/80754af9/r-base_1589917437985/work=/usr/local/src/conda/r-base-3.6.1 -fdebug-prefix-map=/opt/conda/envs/r_3.6.0=/usr/local/src/conda-prefix  -c parse.cpp -o parse.o
parse.cpp:21:10: fatal error: Rcpp/Lightest: No such file or directory
 #include <Rcpp/Lightest>
          ^~~~~~~~~~~~~~~
compilation terminated.
make: *** [/opt/conda/envs/r_3.6.0/lib/R/etc/Makeconf:175: parse.o] Error 1
ERROR: compilation failed for package ‘RcppTOML’
* removing ‘/opt/conda/envs/r_3.6.0/lib/R/library/RcppTOML’
ERROR: dependency ‘RcppTOML’ is not available for package ‘reticulate’
* removing ‘/opt/conda/envs/r_3.6.0/lib/R/library/reticulate’

The downloaded source packages are in
        ‘/tmp/Rtmp2nCFwR/downloaded_packages’
Updating HTML index of packages in '.Library'
Making 'packages.html' ... done
Warning messages:
1: In install.packages("reticulate") :
  installation of package ‘RcppTOML’ had non-zero exit status
2: In install.packages("reticulate") :
  installation of package ‘reticulate’ had non-zero exit status
Error in library(reticulate) : there is no package called ‘reticulate’
Execution halted
[{'status': 'ok', 'doi': 'doi:10.7910/DVN/U3QJQZ', 'fileid': 'all'}]
```

https://github.com/mamba-org/mamba/issues/640#issuecomment-749044745

```
 => RUN conda install mamba -n base -c conda-forge
 => RUN mamba create -y --name r_3.6.0 r-base=3.6.0 r-esse...
------
 > [13/23] RUN mamba create -y --name r_3.6.0 r-base=3.6.0 r-essentials r-reticulate r-r.utils:
#0 6.022 
#0 6.022 # >>>>>>>>>>>>>>>>>>>>>> ERROR REPORT <<<<<<<<<<<<<<<<<<<<<<
#0 6.022 
#0 6.022     Traceback (most recent call last):
#0 6.022       File "/opt/conda/lib/python2.7/site-packages/conda/exceptions.py", line 1079, in __call__
#0 6.022         return func(*args, **kwargs)
#0 6.022       File "/opt/conda/lib/python2.7/site-packages/mamba/mamba.py", line 522, in exception_converter
#0 6.022         raise e
#0 6.022     RuntimeError: Did not find key as expected!
#0 6.022 
#0 6.022 `$ /opt/conda/bin/mamba create -y --name r_3.6.0 r-base=3.6.0 r-essentials r-reticulate r-r.utils`
#0 6.022 
#0 6.022   environment variables:
#0 6.022                  CIO_TEST=<not set>
#0 6.022                CONDA_ROOT=/opt/conda
#0 6.022                      PATH=/opt/conda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin
#0 6.022                           :/bin
#0 6.022        REQUESTS_CA_BUNDLE=<not set>
#0 6.022             SSL_CERT_FILE=<not set>
#0 6.022 
#0 6.022      active environment : None
#0 6.022        user config file : /root/.condarc
#0 6.022  populated config files : 
#0 6.022           conda version : 4.8.3
#0 6.022     conda-build version : not installed
#0 6.022          python version : 2.7.16.final.0
#0 6.022        virtual packages : __glibc=2.28
#0 6.022        base environment : /opt/conda  (writable)
#0 6.022            channel URLs : https://repo.anaconda.com/pkgs/main/linux-64
#0 6.022                           https://repo.anaconda.com/pkgs/main/noarch
#0 6.022                           https://repo.anaconda.com/pkgs/r/linux-64
#0 6.022                           https://repo.anaconda.com/pkgs/r/noarch
#0 6.022           package cache : /opt/conda/pkgs
#0 6.022                           /root/.conda/pkgs
#0 6.022        envs directories : /opt/conda/envs
#0 6.022                           /root/.conda/envs
#0 6.022                platform : linux-64
#0 6.022              user-agent : conda/4.8.3 requests/2.23.0 CPython/2.7.16 Linux/5.15.0-67-generic debian/10 glibc/2.28
#0 6.022                 UID:GID : 0:0
#0 6.022              netrc file : None
#0 6.022            offline mode : False
------
Dockerfile:19
--------------------
  17 |     RUN conda install mamba -n base -c conda-forge
  18 |     #RUN mamba create -y --name r_3.2.1 -c conda-forge r-base=3.2.1 r-essentials r-reticulate r-r.utils
  19 | >>> RUN mamba create -y --name r_3.6.0 r-base=3.6.0 r-essentials r-reticulate r-r.utils
  20 |     RUN mamba create -y --name r_4.0.1 -c conda-forge r-base=4.0.1 r-essentials r-reticulate r-r.utils
  21 |     
--------------------
ERROR: failed to solve: process "/bin/sh -c mamba create -y --name r_3.6.0 r-base=3.6.0 r-essentials r-reticulate r-r.utils" did not complete successfully: exit code: 1
```

https://play.d2lang.com/?script=lFOxchMxEO3vK96YhhS5cUKOQgVNKPGEMVCfZXlta9BphaQjeEj-nZHOztmRDUNxxe6-fbv39ml_UYHfFeA8Lw11QwDk6YcASOcRmLxZr5umaSY5-1wNX2DTJwv8o7VpUvNx63NVKWktx1bbEKUxraeoVW9kJIGnblUB9xmAxR5RO6m-yw2Ft5MRO7laVBXg6UevPQXMlXNfH2afqqfL_HW-o0Cyr7QbQ3-BZp3EQaGqUmxXcgQq5yJ3RuBbIOQaImNfHpc533UgP4hYsB8pcpZ_BFzsvDSjo479TuA-c_reBnAfwWsMlRNYoUIfqO1kt5QCXx51VNs9T2TMUnoElPNzunW7WzFgsWIKSIcOvXPsIz7v4pYtbkdoscBKB7k01OYt1-w3JPBxyEFtpbVkBrmuc_EM_sxiOgRtN62_m94IzHFXT-sb6AC2ZgdtTwiPwcV2G24fddxyH9vM9ZAIPDmjlYyEuCXM8a5-X09Bv0jl-eFVV7kfdzq2vu2jNkFgxj8Jvs4R1p670R7lg6nr-mpxQnDGF5feAK4_4JK9xtrglBS_3D4FLyc8NV4qlTfJDUfCpvhUlYLk-J9eL_N__7R_lAXJnwAAAP__&
