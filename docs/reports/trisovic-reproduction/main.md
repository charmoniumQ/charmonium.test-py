---
# https://pandoc.org/MANUAL.html#general-options-1
from: markdown+emoji
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

# Reproducing "A large-scale study on research code quality and execution"

## Introduction

_Note that this manuscript reads properly on printed media, but the embedded hyperlinks provide references to internet resources for an interested reader._

Reproducibility is essential for scientists to scrutinize each other's results and to build form prior work.
With the advent of computational experiments in science, it is natural to ask how much of those computational experiments are reproducible.

Authors set out to answer this question for specific communities in the past [@pimentel_large-scale_2019, @wang_assessing_2021, @collberg_repeatability_2016, @stodden_empirical_2018, @zhao_why_2012, @trisovic_large-scale_2022].
Of these, Collberg et al. [@collberg_repeatability_2016], Stodden et al. [@stodden_empirical_2018], Zhao et al. [@zhao_why_2012], and Trisovic et al. [@trisovic_large-scale_2022] are especially interesting because they study codes used in basic research.
Of these, Zhao et al. [@zhao_why_2012] and Trisovic et al. [@trisovic_large-scale_2022] are automatic re-execution studies of codes found in repositories with the explicit purpose of encouraging reproducibility for scientific codes.
Zhao et al. study the defunct myExperiment repository while Trisovic et al. studies Harvard Dataverse.
As such, we sought to reproduce Trisovic et al.
Not only will reproduction validate the data, but also future research on automatic code cleaning of R scripts could begin by modifying Trisovic et al.'s original experiments.

According to the latest ACM Badging Terms [@acm_inc_staff_artifact_2020], "reproduction" is defined as a different team using the same experimental setup, while "replication" is a different team using a different experimental setup.
This work constitutes a reproduction; we will develop our own experimental infrastructure to ask and answer the same questions.

In Section 2, we describe Dataverse and the original work.
In Section 3, we explain our methodology, especially the ways it differs from the prior work.
In Section 4, we present our results, using the original work's statistical procedure and novel statistical procedures.
In Section 5, we discuss the significance of the results.

## Original work

In this section, we describe Dataverse, the methodology of the original work, and the results of it.

_Dataverse_ is a "software platform for sharing, finding, citing, and preserving research data" [@dataverse_community_developers_dataverse_2023], and _Harvard Dataverse_ is a large instance of Dataverse.
Scientists can upload the code or data used in a publication, and this bundle is called a _dataset_ in Dataverse.
Datasets can be modified, where each modification gets a new two-number version code (e.g., "1.0").
Each dataset gets a DOI, which points to the latest version of that dataset.

In "A large-scale study on research code quality and execution" [@trisovic_large-scale_2022] (henceforth, "the original work"), Trisovic et al. studied codes in Harvard Dataverse according to the following pseudocode:

1. Identify datasets uploaded to Harvard Dataverse that contain R scripts.
2. For each R version:
   1. Once with code-cleaning and once without:
      1. For each Dataset identified in step 1.:
         1. Run a container based on that version and code-cleaning with that Dataset ID

The container, given a Dataset ID, invokes a runner script which does the following:

1. Download the information for the Dataset.
2. For each file in listed in the Dataset information:
   1. Download the file
   2. Check that the hash of the downloaded file is equal to the expected hash in the Dataset information.
   3. If the hash matches, the attempt was successful, otherwise try another attempt.
3. If code-cleaning was enabled at container-build time:
   1. For each R file we downloaded:
      1. Overwrite that script line-by-line.
      2. For each line:
         1. If the line looks like it is importing a library, add the target library to a list, and copy that line over.
         2. If the line looks like a function that is loading a file, make sure the path is relative, and copy that line over.
         3. If the line calls `setwd`, ignore that line.
         4. Otherwise, copy the line over.
4. Install packages in R needed for the analysis.
5. For each R file we downloaded:
   1. Try to run the R file.
   2. If the R script fails, classify its error.
   3. If the error was one of two specific kinds:
      1. Rerun the R file a different way.
   4. Write results to a log file
6. Upload log files to a database.

I will omit the first three and last two research questions from the original work, due to time constraints.
We prioritized research questions realting directly to reproducibility rates.

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

  * The table [@tbl:original] shows that "we see that code cleaning can successfully address some errors" and "there were no cases of code cleaning "breaking" the previously successful code"

* **RQ6**: Are code files designed to be independent of each other or part of a workflow?

  * "If there are one or more files that successfully re-executed in a dataset, we mark that dataset as’success’. A dataset that only contains errors is marked as 'error', and datasets with TLE values are removed. In these aggregated results (dataset-level), 45% of the datasets (648 out of 1447) have at least one automatically re-executable R file. There is no drastic difference between the file-level success rate (40%) and the dataset-level success rate (45%), suggesting that the majority of files in a dataset are meant to run independently. However, the success rate would likely be better had we known the execution order."

* **RQ7**: What is the success rate in the datasets belonging to journal Dataverse collections?

  * The original work "find[s] a slightly higher than average re-execution rate (42% and aggregated 47% instead of 40% and 45%)... Our results suggest that the strictness of the data sharing policy is positively correlated to the re-execution rate of code files"

* How do release dates of R and datasets impact the re-execution rate?

  * "We observe that R 3.6 has the highest success rate per year."

  * "We are unable to draw significant conclusions on whether the old code had more or fewer errors compared to the recent code (especially considering the sample size per year)."
  
* **RQ8**: What is the success rate per research field?

  * "The highest re-execution rates were observed for the health and life sciences."

## Methodology

In this section, we describe the problems with the prior work's methodology, and present our own methodology.

First, we attempted a replication of the original work.
However, the original work had some internal discrepancies and non-reproducible aspects.

Internal discrepancies (ID) include:

* **ID1:** The raw data from the original work contains a different set of datasets (DOIs) for each experimental condition (see Appendix IIB for proof).
  {#tbl:original} also shows this problem, because there are a different number of "Total datasets" for different verisons of R.
  The choice of datasets-to-test is a controlled variable and should held constant when changing experimental conditions, such as versions of R.
  One possible reason for the change is that the runner script can silently crash, and if it does, it will not output results for files after that point (see Appendix IA for more details).
  We could not find a way to tell if the runner script crashed from the released data.
  Changes in the script between versions (see **ID3**) cause these omissions to be inconsistent between versions.

* **ID2:** The runner has two ways of running an R file, 5.1 and 5.3.1 in the above pseudocode.
  The images uploaded to Dockerhub change the version of R for step 5.1 but not 5.3.1 (see Appendix IIC for proof).
  The scripts that fail 5.1 will be rerun in 5.3.1 with the wrong version of R.

* **ID3:** One Docker image must be prepared for each experimental condition, because the image encodes the experimental condition.
  All things not related to that experimental condition should remain unchanged in the images.
  The images have different versions of the runner script and other important files (see Appendix IIA and IID for proof).

* **ID4:** The R 3.2 and 3.6 environments request `r` while the R 4.0 environment requests `r-base` (see the original work's [Dockerfile](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/Dockerfile#L18)).
  `r` depends on `r-base` and `r-recommended`.
  Therefore, the 3.2 and 3.6 environment will have packages that the 4.0 environment does not have.
  Some scripts may succeed in R 3.6 and fail in R 4.0, not because of the R version, but because the difference in installed packages.

Non-replicable (NR) aspects include:

* **NR1:** Datasets in Dataverse can upload a new version, which will get the same DOI (e.g., [doi:10.7910/DVN/U3QJQZ](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/U3QJQZ&version=2.0));
  The code uses the latest version of the dataset in Dataverse (see the original work's [download_dataset.py](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/download_dataset.py#L13)).
  Re-executing the code will be analyzing different experiments.
  There is no record of which version the original work used, but one could filter for versions released prior to the approximate date of the experiment.

* **NR2:** The main script, which is run after the Docker image is built, calls `install.packages(...)`, which installs the latest version of a package at the time of its execution.
  This results in a different software environment in the replication than that in the original work.
  In particular, one line of the runner script, `install.packages(reticulate)`, fails when we attempted it, although it presumably worked in the original work's execution in 2020.
  This is package is installed during the execution of the main script _after_ the image is built, so using the images from Dockerhub will not help this.

* **NR3:** Conda may have hosted R 3.2.1 at some point, but it currently does not (see the [Conda R repository](https://anaconda.org/r/r/files) and [Conda Forge repository](https://anaconda.org/conda-forge/r/files)).
  Therefore, the R environment used by the original work cannot be built.

Hoping to avoid these issues, we decided to do a reproduction instead of a replication.

* We run all of the DOIs under every version of R, avoiding **ID1**. We run all scripts in the dataset even if one fails.
* The original work used the R command, `source(r_file)`, and fell-back on the shell command, `Rscript r_file`, when that failed. TODO: why? We only use `Rscript r_file`. Furthermore, the container for R 4.0 does not contain R 3.6 at all, so there is no chance of confusing versions of R in that container, avoiding **ID2**.
* We re-executed the code without changing it for all experimental conditions avoiding **ID3** and **ID4**.
* Our project logs the version of the code that it uses, avoiding **NR1**.
* Our containers are built using the Nix package manager, which pins the exact version of every dependency used, avoiding **NR2**.
* Nix can archive all of the soruces it pulls from into a replication package, which avoids **NR3**.

The original work uses AWS Batch and AWS DynamoDB, which makes replication more difficult on other platforms.
For this work, we used Dask [@rocklin_dask_2015] to interface to our Azure VMs, and filesystem_spec [@fsspec_authors_filesystem_spec_2023] to interface with Azure storage buckets.
As long as a user can set up a Dask cluster, they can easily import and execute our code.
Meanwhile, filesystem_spec abstracts the local file system, SSH FS, AWS S3, Azure Storage, and several others.

## Results

We began with the 2170 datasets listed in the original work's master list, [get-dois/dataset_dois.txt](https://github.com/atrisovic/dataverse-r-study/blob/master/get-dois/dataset_dois.txt).
Note that the results only contain a subset of these (see **ID1**).

There is a confirmed issue with Harvard Dataverse where the MD5 hash it displays does not match the file that is available for downloading [^dataverse-wrong-hash] [^harvard-dataverse-wrong-hash].
This issue affects 18/2170 ~ 1.5% of the datasets, which we removed from consideration.
The original work also excluded these.

[^dataverse-wrong-hash]: [Issue #9501 on dataverse GitHub](https://github.com/IQSS/dataverse/issues/9501)
[^harvard-dataverse-wrong-hash]: [Issue #37 on dataverse.harvard.edu GitHub](https://github.com/IQSS/dataverse.harvard.edu/issues/37)

We augmented the unlabeled table on Page 4 to contain our results:

```
|                | Without code cleaning     |
|                |                           |
|                | Original work | This work |
|----------------|---------------|-----------|
| Success rate   | 24%           | 10%       |
| Successes      | 952           | 795       |
| Errors         | 2878          | 7489      |
| Timed outs     | 3829          | 3         |
| Total files    | 7659          | 8287      |
| Total datasets | 2071          | 2071      |
```

The biggest difference is that there are many fewer timed-out scripts.
The original work applies a time-limit to 
Like the original work, we use a one-hour timeout on the whole dataset.
We also apply a per-script dataset, which woud get _more_ timeouts than the original.

<!--
We also tested whether the status of scripts where repeatable over three runs.
We excluded the cases where we observed both successes and failures.
We also excluded the cases where we observed failures with different exception types.

| Observed outcomes              | Percent |
|--------------------------------|---------|
| success                        | $X      |
| fail with same exception       | $X      |
| success or fail                | $X      |
| fail with different exceptions | $X      |

-->

We also exclude datasets selected by the original work which do not contain any R scripts.
They may have contained R scripts at the time that the experiments in the original work were executed.

Data analysis differences:

* Apply statistical tests applied to assess significance.

* Note that Trisovic et al. defines success rate as the ratio of success to success plus errors (i.e., excluding timed out codes).

## Discussion

_Can we reproduce the main claims of the paper?_
* How close can we come?
* Do the differences matter?

### What was easy

### What was difficult

### Communication with the original authors

### What would we do differently if we were redoing our reproduction from scratch?
(or maybe this is part of the first two previous subsections?)

## Conclusion

Trisovic et al. establish an important and seminal dataset for large-scale reproducibility studies of modern scientific codes.
We seek to reproduce their work in a way that avoids some internal discrepancies and non-replicability problems.
Our results partially confirm and partially revise the original work.
We hope that this dataset and platform for assessing reproducibility serves future work in reproducibility and automatic bug fixing.

### Lessons learned

_How to make more things reproducible?_
* What would we have liked the original authors to have done differently then?
* What would the original authors likely do differently now (based on newer understanding/practices/tools/etc)?

## Appendix I: Instructions for reproducing

_Source code archive_

## Appendix II: Bugs in the Trisovic runner script

### A: Bug with `source(...)`

Many Dataverse R scripts contain `rm(list=ls())`. This is commonly recommended to clean the R environment [@vanpelt_how_2023].
Unfortunately, this gets `source(..)`ed by `exec_r_files.R`. Note that `rm(...)` and `ls(...)` remove or list variables in the R's global namespace. Then `exec_r_files.R` will fail because it cannot find its own variables.

For example, `doi:10.7910/DVN/XY2TUK` contains two R scripts, `BasSchub_ISQ_Shocks_Figures.R` which contains `rm(list=ls())` and `BasSchub_ISQ_Shocks_ClusterRobust.R` which does not.
The scripts execute in alphabetical order, so `BasSchub_ISQ_Shocks_ClusterRobust.R` gets executed and put in the results.
However, the `BasSchub_ISQ_Shocks_Figures.R` causes a crash and will not appear in the results, for the experiments which have this bug.

3.6-no-cleaning has only the first, so it has this bug (see [`data/run_log_r32_no_env.csv` line 3161](https://github.com/atrisovic/dataverse-r-study/blob/master/analysis/data/run_log_r36_no_env.csv#L3161)).
4.0-no-cleaning has both entries, so it does not have this bug (see [`data/run_log_r40_no_env.csv line 5259`](https://github.com/atrisovic/dataverse-r-study/blob/master/analysis/data/run_log_r40_no_env.csv#L5259)).
This explains some of the discrepancies in **ID1** and is further evidence for **ID3**.

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

### F: Published code does not match what is in the Docker images

[`run_analysis.sh line 14`](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/run_analysis.sh#L14) reads `echo '\n' >> ~/.Rprofile`, which echos a _literal_ backslash followed by lowercase en to the Rprofile.
We had to remove this to get R to start successfully.
This is evidence that the experiments are based on different versions of the code than what is published.

<!--
Also note that there are only four images in Dockerhub that follow the naming convention (see the original works's Dockerhub [u/atrisovic](https://hub.docker.com/u/atrisovic): `aws-image-r40`, `aws-image-r32`, `aws-image-r36-m`, and `aws-image`), but six experimental conditions (three versions of R, with or without code cleaning).
Since the R version and code cleaning is baked in to the Docker image, these should require different images.
-->
