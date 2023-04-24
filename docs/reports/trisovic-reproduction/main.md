# Reproducing "A large-scale study on research code quality and execution"

## Introduction

Reproducibility is essential for scientists to scrutinize contemporary results and to build off of prior work.
With the advent of computational experiments in science, it is natural to ask how much of those computational experiments are reproducible.

Authors set out to answer this question for specific communities in the past [@pimentel_large-scale_2019, @wang_assessing_2021, @collberg_repeatability_2016, @stodden_empirical_2018, @zhao_why_2012, @trisovic_large-scale_2022].
Of these [@collberg_repeatability_2016, @stodden_empirical_2018, @zhao_why_2012, @trisovic_large-scale_2022] are especially interesting because they study codes used in basic research.
Of these [@zhao_why_2012, @trisovic_large-scale_2022] are automatic re-execution studies of repositories developed specifically to encourage reproducibility.
It is an interesting question to characterize how these change or influence reproducibility.
Zhao et al. [@zhao_why_2012] study the defunct myExperiment repository while Trisovic et al. [@trisovic_large-scale_2022] studies Harvard Dataverse.
As such, we sought to reproduce Trisovic et al. [@trisovic_large-scale_2022].
This is not only to validate the data, but also future research on automatic code cleaning could begin by modifying Trisovic et al.'s original experiments.

Dataverse is a "software platform for sharing, finding, citing, and preserving research data" [@dataverse_community_developers_dataverse_2023], and Harvard Dataverse is a large instance of Dataverse.
Scientists can upload the code or data used in a publication, and this bundle is called a _Dataset_ in Dataverse.
Datasets can be modified, where each modification gets a new two-digit version (e.g., "1.0").
Each dataset gets a DOI, which points to the latest version of that dataset.

According to the latest ACM Badging Terms[@acm_inc_staff_artifact_202], "reproduction" is defined as a different team using the same experimental setup, while "replication" is a different team using a different experimental setup.
This work constitutes a reproduction; we will develop our own experimental infrastructure to ask and answer the same questions.

_TODO: Lay out the other sections._

## Original work

In "A large-scale study on research code quality and execution" [@trisovic_large-scale_2022], Trisovic et al. studied codes in Harvard Dataverse.

1. Identify datasets uploaded to Harvard Dataverse that contain R scripts.
2. For each R version:
   1. Once with code-cleaning and once without:
      1. For each Dataset identified in step 1.:
         1. Run a container based on that version and code-cleaning with that Dataset ID

The container, given a Dataset ID, invokes a runner script which does the following:

1. Download the information for the Dataset.
2. For each file in listed in the Dataset information:
   1. Download the file
   2. Check that hash of the downloaded file is equal to the expected hash in the Dataset information.
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

The authors ask the following research questions:

* What is the code re-execution rate?
  * The original work gives the following table:

    |                | Without code cleaning | With code cleaning | Best of both |
    |----------------|-----------------------|--------------------|--------------|
    | Success rate   | 24%                   | 40%                | 56%          |
    | Successes      | 952                   | 1472               | 1581         |
    | Errors         | 2878                  | 2223               | 1238         |
    | Timed outs     | 3829                  | 3719               | 5790         |
    | Total files    | 7659                  | 7414               | 8609         |
    | Total datasets | 2071                  | 2085               | 2109         |

    Table: Unlabeled table from the original work, page 7. {#tbl:original}

* Can automatic code cleaning with small changes to the code aid in its re-execution?

  * The table [@tbl:original] shows that "we see that code cleaning can successfully address some errors" and "there were no cases of code cleaning "breaking" the previously successful code"

* Are code files designed to be independent of each other or part of a workflow?

  * "If there are one or more files that successfully re-executed in a dataset, we mark that dataset as’success’. A dataset that only contains errors is marked as 'error', and datasets with TLE values are removed. In these aggregated results (dataset-level), 45% of the datasets (648 out of 1447) have at least one automatically re-executable R file. There is no drastic difference between the file-level success rate (40%) and the dataset-level success rate (45%), suggesting that the majority of files in a dataset are meant to run independently. However, the success rate would likely be better had we known the execution order."

* What is the success rate in the datasets belonging to journal Dataverse collections?

  * The original work "find[s] a slightly higher than average re-execution rate (42% and aggregated 47% instead of 40% and 45%)... Our results suggest that the strictness of the data sharing policy is positively correlated to the re-execution rate of code files"

* How do release dates of R and datasets impact the re-execution rate?

  * "We observe that R 3.6 has the highest success rate per year."

  * "We are unable to draw significant conclusions on whether the old code had more or fewer errors compared to the recent code (especially considering the sample size per year)."
  
* What is the success rate per research field?

  * "The highest re-execution rates were observed for the health and life sciences."

## Methodology

First, we attempted a replication of the original work.
However, the original work had some internal discrepancies and non-reproducible aspects.

Internal discrepancies (ID) include:

* **ID1:** The raw data from the original work contains a different set of datasets (DOIs) for each experimental condition (try running this[^different-set-of-dois]).
  This difference is also present in {#tbl:original}.
  The choice of datasets-to-test is a controlled variable and should held constant when changing experimental conditions.
  One possible reason for the change is that the runner script can silently crash, and if it does, it will not output results for files after that point.
  There is no way to tell from the released data if the runner script crashed.

[^different-set-of-dois]:
```python
>>> import requests, csv
>>> url_prefix = "https://raw.githubusercontent.com/atrisovic/dataverse-r-study/master"
>>> all_dois = requests.get(f"{url_prefix}/get-dois/dataset_dois.txt").text.strip().split("\n")
>>> def get_dois(data_file):
...     reader = csv.reader(requests.get(f"{url_prefix}/analysis/data/{data_file}").text.split("\n"), delimiter="\t")
...     return set(row[0] for row in reader if len(row) > 1)
>>> dois32 = get_dois("run_log_r32_env_download.csv")
>>> dois36 = get_dois("run_log_r36_env_download.csv")
>>> len(dois32 - dois36) # dois in r32 but not in r36
2
>>> len(dois36 - dois32) # dois in r36 but not in r32
282
```

* **ID2:** The runner has two ways of running an R file, 5.1 (see the [Dockerfile](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/Dockerfile#L24)) and 5.3.1 (see [execute_files.py](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/execute_files.py#L5)) in the above pseudocode.
  The images uploaded to Dockerhub change the version of R for step 5.1 but not 5.3.1 (try running this[^r-version-mismatch]).
  The scripts that fail 5.1 will be rerun in 5.3.1 with the wrong version of R.

[^r-version-mismatch]:
```
$ docker run --rm -it --entrypoint bash atrisovic/aws-image-r32 -c 'cat ~/.bashrc' | grep 'conda activate r_'
conda activate r_3.2.1

$ docker run --rm -it --entrypoint bash atrisovic/aws-image-r32 -c 'cat execute_files.py' | grep 'Rscript'
    p3 = Popen(['/opt/conda/envs/r_4.0.1/bin/Rscript', f], \
```

* **ID3:** One Docker image must be prepared for each experimental condition, because the image encodes the experimental condition.
  All things not related to that experimental condition should remain unchanged in the images.
  However, Diffoscope[@glukhova_tools_2017] shows that the images have slightly different versions of the runner script and other important files (try running this[^different-scripts]).

[^different-scripts]:
```
$ docker pull atrisovic/aws-image-r32
$ docker save --output aws-image-r32.tar atrisovic/aws-image-r32
$ docker pull atrisovic/aws-image-r40
$ docker save --output aws-image-r40.tar atrisovic/aws-image-r40
$ docker run --rm -t -w $PWD -v $PWD:$PWD:ro registry.salsa.debian.org/reproducible-builds/diffoscope *.tar
shows different versions of usr/workdir/exec_r_files.R and other important files
```

* **ID4:** The R 3.2 and 3.6 environments install `r` while the R 4.0 environment installs `r-base` (see [Dockerfile](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/Dockerfile#L18)).
  `r` depends on `r-base` and `r-recommended`.
  Therefore, the 3.2 and 3.6 environment will have packages that the 4.0 environment does not have.
  Some scripts may succeed in R 3.6 and fail in R 4.0, not because of the R version, but because the difference in installed packages.

Non-reproducible (NR) aspects include:

* **NR1:** Datasets in Dataverse can upload a new version, which will get the same DOI (e.g., [this dataset](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/U3QJQZ&version=2.0));
  The code uses the latest version of the dataset in Dataverse (e.g., [download_dataset.py](https://github.com/atrisovic/dataverse-r-study/blob/master/docker/download_dataset.py#L13)).
  Re-executing the code will be analyzing different experiments.
  There is no record of which version the original work used, but one could filter for versions released prior to the approximate date of the experiment.

* **NR2:** `apt-get update` in the Dockerfile fails.
  There has been a new major release of Debian since the time of experimentation.
  When there is a new release, the source repository changes its information.
  `apt-get` refuses to update when the information is changed.
  Note that `--allow-releaseinfo-change` bypasses this check.
  
  Using the Docker images uploaded to Dockerhub instead of rebuilding them would bypass this issue, but it raises its own issue:
  There are four images in Dockerhub that follow the naming convention, (`aws-image-r40`, `aws-image-r32`, `aws-image-r36-m`, and `aws-image`), but six experimental conditions (3 versions of R, with or without code cleaning).
  Since the R version and code cleaning is baked in to the Docker image, these should require different images.

* **NR3:** The main script, which is run after the Docker image is built, calls `install.packages(...)`, which installs the latest version of a package at the time of its execution.
  This results in a different software environment in the replication than that in the original work.
  In particular, one line of the runner script, `install.packages(reticulate)`, fails when we attempted it.

* **NR3:** Conda may have hosted R 3.2.1 at some point, but it currently does not (see the [Conda R repository](https://anaconda.org/r/r/files) and [Conda Forge repository](https://anaconda.org/conda-forge/r/files)).
  Therefore, the R environment used by the original work cannot be built.

Hoping to avoid these issues, we decided to do a reproduction instead of a replication.

Our container, given a Dataset ID, does the following:

1. If code-cleaning was enabled at run-time:
   1. For each R file:
      1. Overwrite that script line-by-line.
      2. For each line:
         1. If the line looks like it is importing a library, add the target library to a list, and copy that line over.
         2. If the line looks like a function that is loading a file, make sure the path is relative, and copy that line over.
         3. If the line calls `setwd`, ignore that line.
         4. Otherwise, copy the line over.
2. For each R file:
   1. Try to run the R file.
   2. Write results to the disk.

To build the container, we use Nix to build a reproducible Docker image.
Unlike `apt-get`, whose repositories can change mutate incompatibly (see **NR2**), and Conda, whose repositories can pull packages (see **NR4**), Nix finds versions on the the upstream GitHub release page.
Nix can download and archive the sources from which the container is built (transitive inputs), ensuring long-term reproducibility on any platform with basic utilities (C compiler, Zip).

## Results

Data analysis differences:

* Check for non-repeatable errors

* Apply statistical tests applied to assess significance.

* Note that Trisovic et al. defines success rate as the ratio of success to success plus errors (i.e., excluding timed out codes).

## Discussion

### What was easy

### What was difficult

### Communication with the original authors

### What would we do differently if we were redoing our reproduction from scratch?
(or maybe this is part of the first two previous subsections?)

## Conclusion

_Can we reproduce the main claims of the paper?_
* How close can we come?
* Do the differences matter?

### Lessons learned

_How to make more things reproducible?_
* What would we have liked the original authors to have done differently then?
* What would the original authors likely do differently now (based on newer understanding/practices/tools/etc)?

## Appendix I: Instructions for reproducing

_Source code archive_

[1]: https://www.acm.org/publications/badging-terms
