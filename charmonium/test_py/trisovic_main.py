import datetime
import pathlib
import io
import csv
import textwrap
from typing import Mapping
import collections

import dask
import tqdm
import requests
import charmonium.cache

from .analyses.measure_command_execution import CompletedContainer, measure_docker_execution
from .analyses.file_bundle import FileBundle
from .util import create_temp_dir
from .dask_utils import load_or_compute_remotely, compute, group
from . import config


@charmonium.cache.memoize(group=group)
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


@charmonium.cache.memoize(group=group)
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


if __name__ == "__main__":
    dask_client = config.dask_client()
    dois = get_dois()
    n_dois = 3000
    print(f"Dispatching jobs")
    results = dask.compute(*(analyze(doi) for doi in dois[:n_dois]))
    trisovic_results = get_trisovic_results(r_version="4.0", env_clean=False)
    statuses = collections.defaultdict(lambda: 0)
    print(f"Collecting results")
    for doi, (proc, result) in zip(dois, tqdm.tqdm(results)):
        if proc.exit_code != 0:
            print(doi, "run failed")
            print("stdout=\n{textwrap.indent(proc.stdout_b.decode(), '  ')}")
            print("stderr=\n{textwrap.indent(proc.stderr_b.decode(), '  ')}")
            print()
            statuses["run failed"] += 1
        elif (
                (run_log_file := result.files.get(pathlib.Path("run_log.csv"), None))
                and run_log_file is not None
                and (run_log_txt := run_log_file.contents)
                and run_log_txt is not None
        ):
            my_files = set()
            for this_doi, file, *msg_parts in csv.reader(io.StringIO(run_log_txt.decode())):
                assert this_doi == doi
                my_msg = ",".join(msg_parts)
                my_files.add(file)
                their_msg = trisovic_results.get(doi, {}).get(file, None)
                if their_msg != my_msg:
                    print(doi, file, "different msg")
                    print(f"theirs={their_msg!r}")
                    print(f"mine={my_msg!r}")
                    print()
                    statuses["different msg"] += 1
                else:
                    statuses["match"] += 1
            their_files = trisovic_results[doi].keys()
            if my_files != their_files:
                print(doi, "different files")
                print(f"{my_files - their_files}=", f"{their_files - my_files}=", sep="\n")
                print()
                statuses["file mismatch"] += 1
        else:
            print(doi, "has no run log")
            print()
            statuses["doi missing in Trisovic"] += 1
    print(statuses)
