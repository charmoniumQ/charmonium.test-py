FROM ghcr.io/mamba-org/micromamba:1.4.0-alpine

# Note that we are not root here, and this is good.
# https://stackoverflow.com/questions/68155641/should-i-run-things-inside-a-docker-container-as-non-root-for-safety
#RUN whoami

ARG r_ver=3.6.1
RUN micromamba install \
  --name base \
  --channel anaconda \
  --channel r \
  --channel conda-forge \
  --yes \
  r-base=$r_ver \
  r-essentials \
  r-reticulate \
  r-r.utils \
  coreutils \
  time \
  python

COPY exec_r_files.R /exec_r_files.R
COPY execute_files.py /execute_files.py
COPY readability_analysis.py /readability_analysis.py
ENTRYPOINT /bin/bash
