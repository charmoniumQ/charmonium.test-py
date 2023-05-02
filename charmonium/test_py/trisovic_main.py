import sys
import datetime
import pathlib
import io
import csv
import textwrap
from typing import Mapping, cast
import collections

import dask
import tqdm
import requests
import charmonium.cache

from .analyses.measure_command_execution import CompletedContainer, measure_docker_execution
from .analyses.file_bundle import FileBundle
from .util import create_temp_dir
from .dask_utils import load_or_compute_remotely, compute
from . import config


@charmonium.cache.memoize(group=config.memoized_group)
def get_dois() -> list[str]:
    return requests.get("https://raw.githubusercontent.com/atrisovic/dataverse-r-study/master/get-dois/dataset_dois.txt").text.strip().split("\n")


image = "wfregtest.azurecr.io/trisovic-runner:commit-b7171f61-1681765077"


@load_or_compute_remotely
def analyze(doi: str) -> tuple[CompletedContainer, FileBundle]:
    with create_temp_dir() as temp_dir:
        proc = measure_docker_execution(
            image,
            ("./run_analysis.sh", doi, "", str(temp_dir)),
            wall_time_limit=datetime.timedelta(minutes=30),
            mem_limit=1024**3,
            cpus=1.0,
            readwrite_mounts=((temp_dir, pathlib.Path("/results")),),
        )
        try:
            result = FileBundle.from_path(temp_dir, compress=False)
        except Exception as exc:
            raise RuntimeError(f"{temp_dir=} {list(temp_dir.iterdir())=}") from exc
        return proc, result


@charmonium.cache.memoize(group=config.memoized_group)
def get_trisovic_results(r_version: str, env_clean: bool) -> Mapping[str, Mapping[str, str]]:
    # run_log_r40_no_env.csv
    url = f"https://raw.githubusercontent.com/atrisovic/dataverse-r-study/master/analysis/data/run_log_r{r_version.replace('.', '')}_{'no' if not env_clean else ''}_env.csv"
    results: dict[str, dict[str, str]] = {}
    for line in csv.reader(io.StringIO(requests.get(url).text), delimiter="\t"):
        if len(line) >=3:
            doi, file, *msg = line
            files = results.setdefault(doi, {})
            assert file not in files
            files[file] = "\t".join(msg)
        else:
            print("Cannot parse:", line)
    return results


@charmonium.cache.memoize(group=config.memoized_group)
def get_my_results(first_n: int) -> list[tuple[CompletedContainer, FileBundle]]:
    return cast(
        list[tuple[CompletedContainer, FileBundle]],
        globals()["dask"].compute(*(
            globals()["analyze"](doi)
            for doi in get_dois()[:first_n]
        )),
    )

if __name__ == "__main__":
    dask_client = config.dask_client()
    first_n = int(sys.argv[1] if len(sys.argv) > 1 else 300)
    print(f"Dispatching jobs")
    trisovic_results = get_trisovic_results(r_version="4.0", env_clean=False)
    statuses = collections.defaultdict[str, int](lambda: 0)
    doi_statuses = collections.defaultdict[str, int](lambda: 0)
    print(f"Collecting results")
    dois = get_dois()[:first_n]
    for doi, (proc, result) in zip(dois, get_my_results(first_n)):
        if proc.exit_code != 0:
            doi_statuses["(modified) Trisovic runner failed"] += 1
        elif (
                (run_log_file := result.files.get(pathlib.Path("run_log.csv"), None))
                and run_log_file is not None
                and (run_log_txt := run_log_file.contents)
                and run_log_txt is not None
        ):
            my_results = list(csv.reader(io.StringIO(run_log_txt.decode())))
            my_files = set()
            their_files = trisovic_results[doi].keys()
            all_msgs_match = True
            all_files_match = True
            for this_doi, file, my_msg in my_results:
                assert this_doi == doi
                my_files.add(file)
                their_msg = trisovic_results.get(doi, {}).get(file, None)
                all_msgs_match = all_msgs_match and (my_msg == their_msg)
                if their_msg is None:
                    statuses["file not in Trisovic"] += 1
                    all_files_match = False
                elif their_msg == "success" and my_msg == "success":
                    statuses["both succeed"] += 1
                elif their_msg == "success" and my_msg != "success":
                    statuses["Trisovic succeeds where I fail"] += 1
                elif their_msg != "success" and my_msg == "success":
                    statuses["I succeed where Trisovic fails"] += 1
                elif their_msg == my_msg:
                    statuses["both failed with same error msg"] += 1
                elif their_msg != my_msg:
                    statuses["both failed with different error msg"] += 1
                else:
                    raise RuntimeError("This should be unreachable")
            for file in trisovic_results.get(doi, {}).keys() - my_files:
                statuses["file in Trisovic but not mine"] += 1
                print(doi, file, "in Trisovic but not mine")
                all_files_match = False
            if all_msgs_match and all_files_match:
                doi_statuses["all match with Trisovic"] += 1
            elif (not all_msgs_match) and all_files_match:
                doi_statuses["same files diff msgs from Trisovic"] += 1
            elif not all_files_match:
                doi_statuses["diff files from Trisovic"] += 1
            else:
                raise RuntimeError("Unreachable")
        else:
            doi_statuses["doi missing in Trisovic"] += 1
    print(f"{first_n} DOIs and {sum(statuses.values())} scripts")
    print(statuses)
    print(doi_statuses)
