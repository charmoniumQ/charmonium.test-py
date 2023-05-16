---
# https://pandoc.org/MANUAL.html#general-options-1
from: markdown+emoji+tex_math_dollars
# For all inputs, see: https://pandoc.org/MANUAL.html#general-options
# For Markdown variants, see: https://pandoc.org/MANUAL.html#markdown-variants
# For extensions, see: https://pandoc.org/MANUAL.html#extensions
verbosity: INFO
fail-if-warnings: yes

# https://pandoc.org/MANUAL.html#general-writer-options-1
# template: /path/to/template.tex here
dpi: 300
table-of-contents: no
strip-comments: yes

# https://pandoc.org/MANUAL.html#citation-rendering-1
citeproc: yes
cite-method: citeproc # or natbib or biblatex
# cite-method can be citeproc, natbib, or biblatex. This only affects LaTeX output. If you want to use citeproc to format citations, you should also set ‘citeproc: true’.
bibliography: main.bib
#citation-abbreviations: ab.json
link-citations: yes # in-text citation -> biblio entry
link-bibliography: yes # URLs in biblio
notes-after-punctuation: yes

# https://pandoc.org/MANUAL.html#metadata-variables
title: Reproducing "A large-scale study on research code quality and execution"
author:
- Samuel Grayson
- Darko Marinov
- Reed Milewicz
- Daniel S. Katz
date: 2023-05-03
lang: en-US
dir: ltr
standalone: yes # setting to yes calls \maketitle
number-sections: yes

# https://pandoc.org/MANUAL.html#variables-for-latex
documentclass: article
hyperrefoptions:
- linktoc=all
- pdfwindowui
- pdfpagemode=FullScreen
indent: yes
pagestyle: plain
papersize: letter
lof: no # list of figures
lot: no # list of tables
thanks: no
toc: no
# toc-depth: 
filecolor: blue
citecolor: blue
urlcolor: blue
toccolor: blue

# HTML and LaTeX options
fontsize: 12pt
# mainfont: 
# sansfont:
# monofont:
# mathfont:
colorlinks: yes
linkcolor: blue
linestretch: 1.25
margin-left: 1.5in
margin-right: 1.5in
margin-top: 1.5in
margin-bottom: 1.5in

header-includes:
  - \usepackage{setspace}
  - \singlespacing
# include-before: # before body
# include-after: # after body

# https://pandoc.org/MANUAL.html#math-rendering-in-html-1
html-math-method:
  method: katex
# document-css: test.css

---

# Replicating "A large-scale study on research code quality and execution"

## Abstract

We attempt to replicate the dataset from "A large-scale study on research code quality and execution" by Trisovic et al. using our own experimental infrastructure.
Our results agree in part, disagree in part, and extend the original results.
We designed our experimental infrastructure to be extensible for other kinds of replication studies, where one wants to run a set of codes with a certain interpreter and examine the results.
With insight from the original work and its replication, we have attempted to make our infrastructure open-source and reproducible on a large variety of platforms.

## Introduction

_Note that this manuscript reads properly on printed media, but the embedded hyperlinks provide references to internet resources for an interested reader._

Reproducibility is essential for scientists to scrutinize each other's results and to build from prior work.
With the advent of computational experiments in science, it is natural to ask what fraction of those computational experiments are reproducible.

Authors have attempted to answer this question for specific communities in the past [@pimentel_large-scale_2019, @wang_assessing_2021, @collberg_repeatability_2016, @stodden_empirical_2018, @zhao_why_2012, @trisovic_large-scale_2022].
Of these, Collberg et al. [@collberg_repeatability_2016], Stodden et al. [@stodden_empirical_2018], Zhao et al. [@zhao_why_2012], and Trisovic et al. [@trisovic_large-scale_2022] are especially interesting because they study codes used in basic research.
Of these, Zhao et al. [@zhao_why_2012] and Trisovic et al. [@trisovic_large-scale_2022] are automatic re-execution studies of codes found in repositories that have the explicit purpose of encouraging reproducibility for scientific codes.
Zhao et al. studied the defunct myExperiment repository while Trisovic et al. studied Harvard Dataverse.
As such, we sought to reproduce Trisovic et al.
Not only will reproduction validate the data, but also future research on automatic code cleaning of R scripts could begin by modifying Trisovic et al.'s original experiments.

According to the latest ACM Badging Terms [@acm_inc_staff_artifact_2020], "reproduction" is defined as a different team using the same experimental setup, while "replication" is a different team using a different experimental setup.
This work constitutes a reproduction; we will develop our own experimental infrastructure to ask and answer the same questions.

In Section 2, we describe Dataverse and the original work.
In Section 3, we explain our methodology, especially the ways it differs from the prior work.
In Section 4, we present our results, using the original work's statistical procedure and novel statistical procedures.
In Section 5, we discuss the significance of the results.

## Original work

In this section, we describe Dataverse, the methodology of the original work, and its results.

_Dataverse_ is a "software platform for sharing, finding, citing, and preserving research data" [@dataverse_community_developers_dataverse_2023], and _Harvard Dataverse_ is a large instance of Dataverse.
Scientists can upload the code or data used in a publication; this bundle is called a _dataset_ in Dataverse.
Datasets can be modified, where each modification gets a new two-number version code (e.g., "1.0").
Each dataset is given a DOI, which points to the latest version of that dataset.

In "A large-scale study on research code quality and execution" [@trisovic_large-scale_2022] (henceforth, "the original work"), Trisovic et al. studied codes in Harvard Dataverse according to the following pseudocode:

1. Identify datasets uploaded to Harvard Dataverse that contain R scripts.
2. For each R version:
   1. Once with code-cleaning and once without:
      1. For each Dataset identified in step 1.:
         1. Run a container based on that version and code-cleaning with that Dataset ID

The container, given a Dataset ID, invokes a runner script that does the following:

1. Download the information for the Dataset.
2. For each file in listed in the Dataset information:
   1. Download the file
   2. Check that the hash of the downloaded file is equal to the expected hash in the Dataset information.
   3. If the hash matches, the attempt was successful, otherwise try another attempt.
3. If code-cleaning was enabled at container-build time:
   1. For each R file we downloaded:
      1. Run the code-cleaning operation.
4. Install packages in R needed for the analysis.
5. For each R file we downloaded:
   1. Try to run the R file.
   2. If the R script fails, classify its error.
   3. If the error was one of two specific kinds:
      1. Rerun the R file a different way.
   4. Write results to a log file
6. Upload log files to a database.

Here we examine research questions four and five from the original work.
We prioritized looking at these research questions as they relate directly to reproducibility rates.

* **RQ4**: What is the code re-execution rate?
  * The original work gives the following table:

    |                | Without code cleaning | With code cleaning | Best of both |
    |----------------|-----------------------|--------------------|--------------|
    | Success rate   | 24%                   | 40%                | 56%          |
    | Successes      | 952                   | 1472               | 1581         |
    | Errors         | 2878                  | 2223               | 1238         |
    | Timed outs     | 3829                  | 3719               | 5790         |
    | Total files    | 7659                  | 7414               | 8609         |
    | Total datasets | 2071                  | 2085               | 2109         |

    Table: Unlabeled table from the original work, page 7 of the PDF version. {#tbl:original}

* **RQ5**: Can automatic code cleaning with small changes to the code aid in its re-execution?

  * The table [@tbl:original] shows that "we see that code cleaning can successfully address some errors" and "there were no cases of code cleaning "breaking" the previously successful code."

<!--
* **RQ6**: Are code files designed to be independent of each other or part of a workflow?

  * "If there are one or more files that successfully re-executed in a dataset, we mark that dataset as’success’. A dataset that only contains errors is marked as 'error', and datasets with TLE values are removed. In these aggregated results (dataset-level), 45% of the datasets (648 out of 1447) have at least one automatically re-executable R file. There is no drastic difference between the file-level success rate (40%) and the dataset-level success rate (45%), suggesting that the majority of files in a dataset are meant to run independently. However, the success rate would likely be better had we known the execution order."

* **RQ7**: What is the success rate in the datasets belonging to journal Dataverse collections?

  * The original work "find[s] a slightly higher than average re-execution rate (42% and aggregated 47% instead of 40% and 45%)... Our results suggest that the strictness of the data sharing policy is positively correlated to the re-execution rate of code files"

* How do release dates of R and datasets impact the re-execution rate?

  * "We observe that R 3.6 has the highest success rate per year."

  * "We are unable to draw significant conclusions on whether the old code had more or fewer errors compared to the recent code (especially considering the sample size per year)."
  
* **RQ8**: What is the success rate per research field?

  * "The highest re-execution rates were observed for the health and life sciences."
-->

## Methodology

In this section, we describe the problems we have observed with the prior work's methodology, and present our own methodology.

First, we attempted a replication of the original work.
However, we found that the original work had some internal discrepancies and some non-reproducible aspects.

Internal discrepancies (ID) include:

* **ID1:** The raw data from the original work contains a different set of datasets (DOIs) for each experimental condition (see Appendix IIB) and different scripts for each DOI.
  {#tbl:original} also shows this problem, because there are a different number of "Total datasets" for different verisons of R.
  The choice of datasets-to-test is a controlled variable and should held constant when changing experimental conditions, such as versions of R.
  One possible reason for the change is that the runner script can silently crash, and if it does, it will not output results for files after that point (see Appendix IA for more details).
  We could not find a way to tell if the runner script crashed from the released data.
  Changes in the script between versions (see **ID3**) cause these omissions to be inconsistent between versions.

  When we consulted the authors of the original work about this, they speculated that there were intermittent errors.
  The original work computes statistics on the set-intersection of the DOIs in each experimental condition.
  However, even the scripts within a DOI can be reported differently between experimental conditions (see Appendex IIA).

* **ID2:** The runner has two ways of running an R file, 5.1 and 5.3.1 in the above pseudocode.
  The images uploaded to Dockerhub change the version of R for step 5.1 but not 5.3.1 (see Appendix IIC).
  The scripts that fail 5.1 will be rerun in 5.3.1 with the wrong version of R.

* **ID3:** One Docker image must be prepared for each experimental condition, because the image encodes the experimental condition.
  All things not related to that experimental condition should remain unchanged in the images.
  The images have different versions of the runner script and other important files (see Appendix IIA and IID).
  <!-- TODO: remove this -->

* **ID4:** The R 3.2 and 3.6 environments request `r` while the R 4.0 environment requests `r-base` (see the original work's [Dockerfile](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/Dockerfile#L18)).
  `r` depends on `r-base` and `r-recommended`.
  Therefore, the 3.2 and 3.6 environment will have packages that the 4.0 environment does not have.
  Some scripts may succeed in R 3.6 and fail in R 4.0, not because of the R version, but because the difference in installed packages.

* **ID5:** There is a bug in the data-processing scripts that cause the number of scripts with "time limit exceeded" to be over-reported.
  See Appendix IIF for details. 

Non-replicable (NR) aspects include:

* **NR1:** Datasets in Dataverse can upload a new version, which will be given the same DOI (e.g., [doi:10.7910/DVN/U3QJQZ](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/U3QJQZ&version=2.0));
  The code uses the latest version of the dataset in Dataverse (see the original work's [download_dataset.py](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/download_dataset.py#L13)).
  Re-executing the code will analyze different experiments.
  There is no record of which version the original work used, but one could filter for versions released prior to the approximate date of the experiment.
  
  The authors of the original work believe this is desirable because the latest version of the dataset will be the most complete and most likely to work.

* **NR2:** The main script, which is run after the Docker image is built, calls `install.packages(...)`, which installs the latest version of a package at the time of its execution.
  This results in a different software environment in the replication than that in the original work.
  In particular, one line of the runner script, `install.packages(reticulate)`, fails when we attempted it, although it presumably worked in the original work's execution in 2020.
  This package is installed during the execution of the main script _after_ the image is built, so using the images from Dockerhub will not help this.

* **NR3:** Conda may have hosted R 3.2.1 at some point, but it currently does not (see the [Conda R repository](https://anaconda.org/r/r/files) and [Conda Forge repository](https://anaconda.org/conda-forge/r/files)).
  Therefore, the R environment used by the original work cannot be built.

We communicated with the authors about **ID1** and **NR1**.[^Before the camera-ready version, we intend to communicate with the authors on all of these concerns.]

### Our infrastructure

To try to avoid these issues, we decided to do a reproduction instead of a replication.

Our experimental infrastructure defines the following class interfaces:



Our experimental infrastructure contains a function which executes four phases:

1. Get codes from registry. A registry, abstractly, is a list of codes to test. It could be a GitHub repository search query or in this case a fixed list of references to Harvard Dataverse. It returns a `Code` object, which is something that can be downloaded to a directory.
2. Analyze codes An analysis is any procedure that consumes an experimental condition and a code to produce a result. This could be a static analysis or dynamic analysis. Running the code is a particular example of a dynamic analysis. This execution can be distributed across nodes in a cluster.
3. Reduce reuslts. The results produced by the analysis could be too big to send back to a single node, so the results are reduced by another step. Decoupling reducing from analyzing means one can revise the reducer without having to re-evaluate the analyzer. This reduction can be distributed as well.
4. Aggregate results. The reduced results are sent back to a single node and aggregated together.

There are so many codes from Harvard Dataverse to test, that we need to utilize distributed computing, but we do not want our infrastructure to be limited to a specific computing platform.
The original work uses AWS Batch and AWS DynamoDB, which makes replication more difficult on other platforms.
For this work, we used Dask [@rocklin_dask_2015] to interface to our Azure VMs, and filesystem_spec [@fsspec_authors_filesystem_spec_2023] to interface with Azure storage buckets.
As long as a user can set up a Dask cluster, they can easily import and execute our code.
Meanwhile, filesystem_spec abstracts the local file system, SSH FS, AWS S3, Azure Storage, and several others.

The above infrastructure is generally applicable to any automatic reproducibility study, so long as the user can provide:

1. A list of registries in which to find codes to test.
2. A list of experimental conditions to try.
3. An analysis to run on each experimental condition and code.
4. A reduction to run on each analysis result.
5. An aggregation to run on the result of reducing-and-analyzing.

Besides this general infrastructure, we have specific configuration for our case:

We use a Docker container in the analysis step.
Our Docker image is built by Nix, so it can be bit-by-bit reproduced by other users.
Our Docker image contains the specified R version, the "recommended" R packages, GNU coreutils, findutils, Make, time, and common system libraries.
Without common system libraries, such as zlib, almost all of the dataset scripts fail, because the configure scripts of the packages that they install to bootstrap the environment expect certain system libraries (like zlib) to exist.
The R package manager is not capable of managing system-level libraries in the UNIX Filesystem Hierarchy Standard (FHS), because R runs as user, but the relevant parts of the UNIX FHS is usually owned by root.
We decided to include all libraries that the scripts depended on (discovered by trial-and-error) that are within the top 5,000 most popular packages according to the Debian Popularity contest.
This is a reasonable expectation of what real user systems might have installed.

While we wanted to use the exact versions of R used by the original work, Nix does not have 4.0.1, so we used 4.0.2; there is a bug with Nix's version of R MASS in 3.2.1, so we used 3.2.3.

## Results

We began with the 2170 datasets listed in the original work's master list, [get-dois/dataset_dois.txt](https://github.com/atrisovic/dataverse-r-study/blob/master/get-dois/dataset_dois.txt).
In the interest of time, we took a random sample of one tenth of these datasets (217).
Note that the original work's results only contain a subset of these (see **ID1**), therefore the denominator of the original work will be different in different columns.

There is a confirmed issue with Harvard Dataverse where the MD5 hash it displays does not match the file that is available for downloading [^dataverse-wrong-hash] [^harvard-dataverse-wrong-hash].
This issue affects 18/2170 (about 1.5%) of the datasets, which we removed from consideration.
The original work also excluded these.

We also tested whether the status of scripts were repeatable over two runs.
We also excluded the cases where we observed failures with different exception types.

[^dataverse-wrong-hash]: [Issue #9501 on dataverse GitHub](https://github.com/IQSS/dataverse/issues/9501)
[^harvard-dataverse-wrong-hash]: [Issue #37 on dataverse.harvard.edu GitHub](https://github.com/IQSS/dataverse.harvard.edu/issues/37)

\begin{table}
  \begin{tabular}{rcccccc}
     & \multicolumn{2}{c}{No code cleaning} & \multicolumn{2}{c}{Trisovic code cleaning} & \multicolumn{2}{c}{Best of both} \\
     & Original work & This work & Original work & This work & Original work & This work \\
    Success\footnotemark{} & 12% = 952/7659 & 2% = 5/264 & 20% = 1472/7414 & 5% = 13/264 & 18% = 1581/8609 & 5% = 13/264 \\
    Failure & 38% = 2878/7659 & 98% = 259/264 & 30% = 2223/7414 & 95% = 251/264 & 14% = 1238/8609 & 95% = 251/264 \\
    Timed out & 50% = 3829/7659 & 0% = 0/264 & 50% = 3719/7414 & 0% = 0/264 & 67% = 5790/8609 & 0% = 0/264 \\
  \end{tabular}
  \caption{This table rephrases the results from the unlabeled table on Page 7 of the original work and displays the analogous result from this work side-by-side. }
  \label{table:main-results}
\end{table}

\footnotetext{
  The percentage in this row is not analogous to the "success rate" in the original work.
  The original work defines "success rate" as the number of successful scripts divided by the number of successes plus failures.
  The percentage here is the number of successful scripts divided by the total.
  Their definition ignores timed out scripts; if we adopt their definition, then our numbers do not change appreciably (we have few timeouts), but their success rate is 24%.
}

## Discussion

The number of scripts that succeed in this work is markedly lower.

1. Some scripts do not explicitly install their dependencies, but these were by chance found in the environment used in the original work.
  Depending on how one defines "automatically reproducible", not installing dependencies makes the code not automatically reproducible, even if it may succeed coincidentally in some cases.
  This work attempts to be more of a "blank slate" to detect these cases, so it is good that those scripts fail in this work.

2. Many scripts will call `install.packages`, which will install the latest version of a package.
  However, the latest version is not necessarily compatible with the running version of R.
  `install.packages` does not attempt to solve dependency conflicts.
  For example, the latest version, 3.4.2, of popular plotting package ggplot2 requires R 3.3 or newer.
  When Trisovic et al. ran their experiments in 2020, this may not have been the case, so those scripts may have worked.

One major difference is that there are many fewer timed-out scripts.
Both this work and the original work apply a five-hour time-limit to the collection of scripts as a whole and a one-hour time-limit to each individual script (the original work only applies the per-script limit in step 5.1, not in 5.3.1 of the pseudocode; see **ID2** for details).
It would be surprising if half of the scripts in Harvard Dataverse ran for longer than hour, or five hours combined.
We have fewer timeouts because the original work was affected by **ID5**, which overreported the number of timeouts.
Another reason is that the original work does two calls to `install.packages`, which involve compiling C packages for R, quite an expensive operation.
Our runner does not need this `install.packages` call at all, so it does less work against the time-limit.

Despite these differences in the baseline rate, code cleaning does in fact improve the success rate with very few downsides.

## Conclusion

Trisovic et al. established an important and seminal dataset for large-scale reproducibility studies of modern scientific codes.
We seek to reproduce their work in a way that avoids some internal discrepancies and non-replicability problems.
Our results partially confirm and partially revise the original work.
We hope that this dataset and platform for assessing reproducibility serves future work in reproducibility and automatic bug fixing.

### Lessons learned

_How to make more things reproducible?_
* What would we have liked the original authors to have done differently then?
* What would the original authors likely do differently now (based on newer understanding/practices/tools/etc)?

## Appendix I: Instructions for reproducing

The source code for this experiment can be found at <https://github.com/charmoniumQ/charmonium.test-py>

First download and install Nix package manager

```
$ sh <(curl -L https://nixos.org/nix/install) --daemon
$ mkdir -p ~/.config/nix
$ echo "experimental-features = nix-command flakes" >> ~/.config/nix/nix.conf
```

Then use Nix to get a shell for this project. It should have Python3.11

```
$ nix develop
nix-shell$ which python3
/nix/store/blah
```

Customize `data_path`, `index_path`, and `dask_client` in `config.py`.
Note that `upath.UPath` can be a local path, S3 path, SSHFS path, or other storage backends.
If you wish to run locally, make `dask_client` return `distributed.Client()`.
If you wish to run on the cloud, make `dask_client` return a client to the cloud's Dask scheduler, and make sure `index_path` and `data_path` are accessible to the Dask workers.
Run:

```
$ python3 -c from charmonium.test_py.reproduce_trisovic import run; run()'
```

This will use the Docker images I built and host publicly.
If you want to use your own Docker images, set `$DOCKER_REGISTRY` to a registry you can push to.
Run:

```
$ ./dockerfiles/build.sh
$ cat ./dockerfiles/r-runners
```

And set the value of `./charmonium/test_py/workflow_executors/r_lang.py` to point to the Docker images built in the previous step.

## Appendix II: Bugs in the Trisovic runner script

### A: Bug with `source(...)` causes runner to crash

Many Dataverse R scripts contain `rm(list=ls())`. This is commonly recommended to clean the R environment [@vanpelt_how_2023].
Unfortunately, this gets `source(..)`ed by `exec_r_files.R`. Note that `rm(...)` and `ls(...)` remove or list variables in the R's global namespace. Then `exec_r_files.R` will fail because it cannot find its own variables.

For example, `doi:10.7910/DVN/XY2TUK` contains two R scripts, `BasSchub_ISQ_Shocks_Figures.R` which contains `rm(list=ls())` and `BasSchub_ISQ_Shocks_ClusterRobust.R` which does not.
The scripts execute in alphabetical order, so `BasSchub_ISQ_Shocks_ClusterRobust.R` gets executed and put in the results.
However, the `BasSchub_ISQ_Shocks_Figures.R` causes a crash and will not appear in the results, for the experiments which have this bug.

3.6-no-cleaning has only the first, so it has this bug (see [`data/run_log_r32_no_env.csv` line 3161](https://github.com/atrisovic/dataverse-r-study/blob/master/analysis/data/run_log_r36_no_env.csv#L3161)).
On the other hand, 4.0-no-cleaning does not have this bug, so it will have results both scripts (see [`data/run_log_r40_no_env.csv line 5259`](https://github.com/atrisovic/dataverse-r-study/blob/master/analysis/data/run_log_r40_no_env.csv#L5259)).
This explains some of the discrepancies in **ID1** and is further evidence for **ID3**.

<!-- TODO: estimate frequency -->

### B: Different DOIs and files

The following Python session, which you can run for yourself, shows that different DOIs are reported between experimental conditions, which supports **ID1**

\scriptsize
```python
>>> import requests, csv
>>> url_prefix = "https://raw.githubusercontent.com/atrisovic/dataverse-r-study/master"
>>> all_dois = requests.get(f"{url_prefix}/get-dois/dataset_dois.txt").text.strip().split("\n")
>>> def get_dois(data_file):
...     request = requests.get(f"{url_prefix}/analysis/data/{data_file}")
...     reader = csv.reader(request.text.split("\n"), delimiter="\t")
...     return set(row[0] for row in reader if len(row) > 1)
>>> dois32 = get_dois("run_log_r32_env_download.csv")
>>> dois36 = get_dois("run_log_r36_env_download.csv")
>>> len(dois32 - dois36) # dois in r32 but not in r36
2
>>> len(dois36 - dois32) # dois in r36 but not in r32
282
```
\normalsize

This may be caused by:
* transient download errors for one R version but not another;
* cases where [`./download_datasets.py`](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/download_dataset.py) executes partially, but is interrupted by a timeout from [line 17 of `run_analysis`](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/run_analysis.sh#L17).
  Note that while other parts of the script ignore some kinds of download errors, they will not ignore this kind of download error for the reasons explained in the last bullet of Appendix IIF.
* cases where the runner crashes in one R version but not another (one such case is described in Appendix IIA). The return code of the runner is not reported in the original work's dataset, so there is no way to tell on how many cases the runner crashed.

These differences between R versions are exacerbated by different versions of the script, and they make it difficult to compare results across R versions.

### C: Mismatched versions of R

[`Dockerfile` line 24](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/Dockerfile#L24) executes `conda activate ...` to set the R version for [`exec_r_files.R` line 30](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/exec_r_files.R#L30), which `source(...)`es the R script under test.

If that fails, [`exec_r_files.R` line 72](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/exec_r_files.R#L72) calls [execute_files.py line 5](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/execute_files.py#L5), which invokes `Rscript` from a hard-coded path.
This hard-coded path needs to be the proper R version as the former for this method to yield consistent results, but in the published containers, it was not.
This Bash session, which you can run for yourself, shows that the image called `aws-image-r32` used 3.2 for the former, but 4.0 for the latter method, confirming **ID2**.

\scriptsize
```bash
$ docker run --rm -it --entrypoint bash atrisovic/aws-image-r32 -c 'cat ~/.bashrc' | grep 'conda activate r_'
conda activate r_3.2.1
$ docker run --rm -it --entrypoint bash atrisovic/aws-image-r32 -c 'cat execute_files.py' | grep 'Rscript'
    p3 = Popen(['/opt/conda/envs/r_4.0.1/bin/Rscript', f], \
```
\normalsize

### D: Different versions of the script

We can use Diffoscope [@glukhova_tools_2017] to examine the differences between containers.
This Bash session, which you can run for yourself, shows that the images `r32` and `r40` have significant differences in the runner script which contributes to **ID1** and **ID3**.

\scriptsize
```bash
$ docker pull atrisovic/aws-image-r32
$ docker save --output aws-image-r32.tar atrisovic/aws-image-r32
$ docker pull atrisovic/aws-image-r40
$ docker save --output aws-image-r40.tar atrisovic/aws-image-r40
$ docker run --rm -t -w $PWD -v $PWD:$PWD:ro registry.salsa.debian.org/reproducible-builds/diffoscope *.tar
shows different versions of usr/workdir/exec_r_files.R and other important files
```
\normalsize

### E: Original image does not build due to out-of-date Debian version

`apt-get update` in the original work's [`Dockerfile` line 3](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/Dockerfile#L3) fails.
There has been a new major release of Debian since the time of experimentation.
When there is a new release, the source repository changes its information.
`apt-get` refuses to update when the information is changed from the last time it was run.
Changing the line to `apt-get update --allow-releaseinfo-change` allows us to bypass this check.
Presumably the original work intended to use `continuumio/miniconda3` as a base image, but they use `continuum/miniconda` instead, which has not been updated in three years, since before the last Debian major release.

### F: Time limit exceeded is overcounted

The Jupyter Notebook [`02-get-combined-success-rates.ipynb`](https://github.com/atrisovic/dataverse-r-study/blob/master/analysis/02-get-combined-success-rates.ipynb) reads tables where each row is a script, and each column has the result of running that file in a specific R version.
The notebook aggergates the results together, according to rules such as:
- If a script succeeds in any R version, it is considered to succeed.
- If a script times out in any R version and none succeed, it is considered to time out.
- Otherwise, the script is considered to error out.

However there is a bug in that notebook:

1. The notebook [`02-get-combined-success-rates.ipynb`](https://github.com/atrisovic/dataverse-r-study/blob/master/analysis/02-get-combined-success-rates.ipynb), uses an "outer join". Therefore, if a script is absent from one of the R-versions, it will receive NaN in that cell. This occurs in the cells labeled "In[7]" and "In[9]" for the case with code-cleaning, and is duplicated to "In[30]" and "In[32]" for the case without code-cleaning.

  For the sake of example, suppose we have the following results (on different scripts).

  R 3.2 results:

  | File       | Result |
  |------------|--------|
  | script0.R  | error  |
  
  R 3.6 results:
  
  | File       | Result |
  |------------|--------|
  | script1.R  | error  |
  
  Then the outer merge of R 3.2 and 3.6 would be:
  
  | File       | R 3.2 | R 3.6 |
  |------------|-------|-------|
  | script0.R  | NaN   | error |
  | script1.R  | error | NaN   |

2. The cell labeled "In[11]" and "In[34]" assigns the aggregated-result NaN if none of the individual-results are NaN or time-limit-exceeded.
3. The cells labeled "In[17]" and "In[38]" remove datasets that fail to download, but there are other reasons we will discuss below that can cause a script result to be missing.
4. The cell labeled "In[23]" and "In[43]" save the result of the preceding steps as `data/aggregate_results_env.csv`.
5. The cell labeled "In[2]" and "In[5]" of [03-success-dataset-list.ipynb](https://github.com/atrisovic/dataverse-r-study/blob/master/analysis/03-success-dataset-list.ipynb) loads this file, `data/aggregate_results_env.csv`.
6. The cell labeled "In[4]" and "In[7]" of [03-success-dataset-list.ipynb](https://github.com/atrisovic/dataverse-r-study/blob/master/analysis/03-success-dataset-list.ipynb) counts the number of NaNs in the result column.
  This number matches exactly what is put in the unlabeled table on page 7 of the prior work's PDF, so we assume this is their provenance.

If the only way that data can be missing is for a time out, then this approach would be valid.
However, there are other ways that the data may be missing:

* If the runner crashes, it will not write results for some of the scripts.
  We found one condition which causes the runner to crash in Appendix IIA.

* When the time limit is exceeded, [`run_analysis.sh` line 36](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/run_analysis.sh#L36) writes a record saying saying that a file named "unknown" timed out.
  When the the script exits with an error, [`exec_r_files.R` line 88](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/exec_r_files.R#L88) will write t  he actual name of the script and the error.
  Therefore, the outer-join will have two rows indicating a timed out result where it should only have one:

  | File     | R 3.2 | R 3.6     | Result |
  |----------|-------|-----------|--------|
  | unknown  | NaN   | timed out | NaN    |
  | script.R | error | NaN       | NaN    |

* [line 17 of `run_analysis.sh`](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/run_analysis.sh#L17) downloads the dataset from Dataverse with a timeout.
  When this timeout is hit, line 20 writes a record into `run_log.csv` saying that a file named "unknown" experienced an error called "download error".
  Like in the previous case, "unknown" will not exist if another R version succeeds in downloading that dataset, which happens quite often in the dataset.
  While [`02-get-combined-success-rates.ipynb`](https://github.com/atrisovic/dataverse-r-study/blob/master/analysis/02-get-combined-success-rates.ipynb) _does_ exclude download errors found in `run_log_ds.csv`, it does not check for download errors in `run_log.csv`, so it will not exclude this DOI.

<!--
### Published code does not match what is in the Docker images

[`run_analysis.sh line 14`](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/run_analysis.sh#L14) reads `echo '\n' >> ~/.Rprofile`, which echoes a _literal_ backslash followed by lowercase en to the Rprofile.
We had to remove this to get R to start successfully.
This is evidence that the experiments are based on different versions of the code than what is published.

Also note that there are only four images in Dockerhub that follow the naming convention (see the original works's Dockerhub [u/atrisovic](https://hub.docker.com/u/atrisovic): `aws-image-r40`, `aws-image-r32`, `aws-image-r36-m`, and `aws-image`), but six experimental conditions (three versions of R, with or without code cleaning).
Since the R version and code cleaning is baked in to the Docker image, these should require different images.
-->
