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
