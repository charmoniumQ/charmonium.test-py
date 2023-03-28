- For each dataset from Dataverse, does the data record what "version" of that dataset the study uses?
  - If not known, around what date was the study run? Perhaps I can use this the latest version before this date.
- Building the provided Dockerfile fails with the following:
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
  - This is because it is based on continuumio/miniconda, which has not been updated in 3 years, rather than continuumio/miniconda3.
- Installing r-env=3.6.0 with Conda fails with the following:
```
 > [3/3] RUN conda install --name base --channel conda-forge r-base=r_3.6.0 r-essentials:                                                                               
PackagesNotFoundError: The following packages are not available from current channels:

  - r-base=r_3.6.0

Current channels:

  - https://conda.anaconda.org/conda-forge/linux-64
  - https://conda.anaconda.org/conda-forge/noarch
  - https://repo.anaconda.com/pkgs/main/linux-64
  - https://repo.anaconda.com/pkgs/main/noarch
  - https://repo.anaconda.com/pkgs/r/linux-64
  - https://repo.anaconda.com/pkgs/r/noarch

To search for alternate channels that may provide the conda package you're
looking for, navigate to

    https://anaconda.org

and use the search bar at the top of the page.
```
- Why different DOIs for different versions of R?

# Code improvements (not done!)
- Use pyDataverse
- Use AST instead of string search
- Use newer Python in R-runner
