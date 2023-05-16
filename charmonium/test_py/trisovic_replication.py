import json
import csv
import enum
import pathlib
import dataclasses
import random
import functools
import collections
import traceback
import sys
import textwrap
import re
import warnings
import datetime
import itertools
from typing import Iterable, TypeVar, Any, Callable, Mapping, Sequence, Optional, IO, cast, TYPE_CHECKING

import yaml
import requests
import pandas  # type: ignore
import toolz  # type: ignore
import charmonium.cache
import tqdm

from .main import  stream_results, get_results, Config, reduced_analysis, analyze
from .registries import DataverseTrisovicFixed
from .conditions import TrisovicCondition, CodeCleaning
from .analyses.file_bundle import File
from .codes.dataverse_dataset import HashMismatchError
from .codes import WorkflowCode, DataverseDataset
from .analyses import ExecuteWorkflow, WorkflowExecution
from .conditions import TrisovicCondition
from .util import create_temp_dir, flatten1, expect_type, clear_cache, find_last, is_not_none, shorten_lines
from .types import Code, Result, Condition, Registry, Analysis, ReducedResult, Reduction
from . import config


class Work(enum.Enum):
    original_work = "original_work"
    this_work = "this_work"


class ExecutionClass(enum.Enum):
    success = "success"
    failure = "failure"
    timed_out = "timed out"
    unknown = "unknown"


@dataclasses.dataclass(frozen=True)
class Event:
    kind: str
    params: Mapping[str, str]


@dataclasses.dataclass(frozen=True)
class ScriptResult:
    exit_code: int
    stdout: str
    stderr: str
    events: tuple[Event, ...]

    @property
    def execution_class(self) -> ExecutionClass:
        if self.exit_code == 0:
            return ExecutionClass.success
        elif self.exit_code in {124, 128 + 9}:
            # See `man timeout`
            # Timeout can exit with 124 or 128+9
            return ExecutionClass.timed_out
        else:
            return ExecutionClass.failure


@dataclasses.dataclass(frozen=True)
class MyReducedResult(ReducedResult):
    workflow_execution: WorkflowExecution
    script_results: Mapping[str, ScriptResult]
    missing_files: tuple[pathlib.Path, ...]


class MyReduction(Reduction):
    def reduce(self, code: Code, condition: Condition, result: Result) -> MyReducedResult:
        if isinstance(result, WorkflowExecution):
            script_results: dict[str, ScriptResult] = {}
            missing_files: list[pathlib.Path] = []
            if (index_file := result.outputs.files.get(pathlib.Path("index.json"), None)) and index_file is not None and (contents := index_file.contents) and contents is not None:
                results_map = json.loads(contents)
            else:
                results_map = {}
            for r_file, results_str in results_map.items():
                results_path = pathlib.Path(results_str)
                expected_files = {results_path / "stdout", results_path / "stderr"}
                this_missing_files = expected_files - result.outputs.files.keys()
                if this_missing_files:
                    missing_files.extend(this_missing_files)
                    continue
                if (exit_code_file := result.outputs.files.get(results_path / "exit_code", None)) is not None:
                    exit_code = int(expect_type(bytes, exit_code_file.contents).decode())
                else:
                    exit_code = 137
                stderr = expect_type(bytes, result.outputs.files[results_path / "stderr"].contents).decode(errors="backslashreplace")
                stdout = expect_type(bytes, result.outputs.files[results_path / "stdout"].contents).decode(errors="backslashreplace")
                script_results[r_file] = ScriptResult(
                    exit_code=exit_code,
                    stderr=shorten_lines(stderr, 20, 60),
                    stdout=shorten_lines(stdout, 20, 60),
                    events=parse_events(stderr),
                )
            detailed_result = MyReducedResult(
                workflow_execution=WorkflowExecution(**{  # type: ignore
                    **result.__dict__,
                    "logs": result.logs.truncate(1024),
                    "outputs": result.outputs.truncate(1024),
                }),
                script_results=script_results,
                missing_files=tuple(missing_files),
            )
            return detailed_result
        else:
            raise TypeError(type(result))


def print_result(result: WorkflowExecution, fobj: None | IO[str] = None) -> None:
    for label, filebundle in [("outputs", result.outputs), ("logs", result.logs)]:
        print(f"  {label}", file=fobj)
        for path, file in filebundle.files.items():
            contents = file.contents
            if contents is not None:
                printable_contents = contents[:1000].decode(errors="backslashreplace")
            else:
                printable_contents = ""
            print(
                f"    {path} size={file.size} ({label})",
                textwrap.indent(
                    printable_contents,
                    prefix=" " * 6,
                ),
                sep="\n",
                file=fobj,
            )
    for proc in result.procs:
        for label, std_bytes in [("stdout", proc.stdout_b), ("stderr", proc.stderr_b)]:
            print(proc.docker_command)
            print(
                f"  {label}:",
                textwrap.indent(
                    std_bytes.decode(errors="backslashreplace"),
                    prefix=" " * 4,
                ),
                sep="\n",
                file=fobj,
            )

def get_experimental_status(
        result: MyReducedResult | Exception,
) -> str:
        if isinstance(result, MyReducedResult):
            if result.missing_files:
                return "missing files"
            any_failures = False
            all_successes = True
            any_files = False
            for r_file, script_result in result.script_results.items():
                any_files = True
                if script_result.exit_code != 0:
                    any_failures = True
                    all_successes = False
                else:
                    return "normal"
            if not any_files:
                return "no R files"
            elif any_failures:
                return "normal"
            elif all_successes:
                return "all succeed"
            else:
                raise RuntimeError("Exhausted cases")
        elif isinstance(result, HashMismatchError):
            return "hash mismatch"
        elif isinstance(result, Exception):
            return "exception in runner"
        else:
            raise TypeError(type(result))


def parse_events(error_text: str) -> tuple[Event, ...]:
    error_regexes = {
        "r_error": re.compile(
            r"Error(?: in (?P<loc>.*) )?:\s+(?P<msg>\S.*)\n\s*(?:Calls: (?P<calls>.*)\n)?(?:In addition: (?P<in_addition>.*)\nIn (?P<in_addition_loc>.*) :(?:\n  | )(?P<in_addition_msg>.*)\n)?Execution halted",
            re.MULTILINE,
        ),
        "r_warnings": re.compile(
            r"Warning messages:\n(?P<warnings>(?:\d+: In .* :\s+.*\n)*)",
            re.MULTILINE
        ),
        "r_warning": re.compile(
            r"^Warning(?: message:)?(?:\s+[Ii]n (?P<loc>.*))?\s+:\s+(?P<msg>[a-z0-9].*)",
            # Need to exclude "Warning: Fortran ...". R warnings seem always lowercase.
            re.MULTILINE
        ),
        "gcc_fatal_error": re.compile(
            r"(?P<file>.*):(?P<line>\d+):(?P<col>\d+): fatal error: (?P<msg>.*)\n(?P<source>[\s\S]*)\ncompilation terminated",
            re.MULTILINE,
        ),
        "configure_error": re.compile(r"(?P<configure_script>./config(?:ure|.status)): line (?P<line>\d+): (?P<msg>.*)"),
        "make_error": re.compile(
            r"make: \*\*\* \[(?P<makefile>.+):(?P<line>\d+): (?P<target>.*)\] Error (?P<exit_code>\d+)"
        ),
        "ld_error": re.compile(
            r"(?P<ld_path>/[a-zA-Z0-9/]+/ld): (?P<msg>.*)"
        ),
        "r_warning_count": re.compile(r"\nThere were (?P<num_warnings>\d+) warnings"),
        "r_other_error": re.compile(r"ERROR: '(?P<msg>.*)'"),
        "sigkill": re.compile(r"Killed!"),
        "install_r_package": re.compile(r"\* installing \*(?P<type>.*)\* package '(?P<package>.*)' ..."),
        "loaded_r_package": re.compile(r"Loading required package: (?P<package>.*)"),
    }

    r_error_regexes = {
        "no such function": re.compile(r"could not find function \"(?P<function>.*)\""),
        "no such package": re.compile(r"there is no package called '(?P<package>.*)'"),
        "installation of package failed": re.compile(r"installation of package '(?P<package>.*)' had non-zero exit status"),
        "cannot open the connection": re.compile(r"cannot open the connection"),
        "cannot open compressed file": re.compile(r"cannot open compressed file '(?P<file>.*)', probable reason '(?P<reason>.*)'"),
        "package is not available": re.compile(r"package '(?P<package>.*)' is not available \(for R version (?P<r_ver>.*)\)"),
    }

    events: list[tuple[int, Event]] = []
    for error_kind, error_regex in error_regexes.items():
        for match in error_regex.finditer(error_text):
            params = match.groupdict()
            if error_kind == "r_warnings":
                warnings.warn("When r_warnings are coalesced, they are also unparsed.")
                # In principle, we could parse these into individual warnings here.
            elif error_kind == "r_error" or error_kind == "r_warning":
                # replace "msg" with a more parsed alternative
                for r_error_kind, r_error_regex in r_error_regexes.items():
                    if (match2 := r_error_regex.search(match.group("msg"))) is not None:
                        for key, val in match2.groupdict().items():
                            params[key] = val
                        params["subkind"] = r_error_kind
                        del params["msg"]
                        break
            events.append((match.start(), Event(error_kind, params)))
    return cast(
        tuple[Event, ...],
        tuple(map(toolz.second, sorted(events))),
    )


orig_work_dict = {
    CodeCleaning.none: {
        ExecutionClass.success: 952,
        ExecutionClass.failure: 2878,
        ExecutionClass.timed_out: 3829,
        ExecutionClass.unknown: 0,
    },
    CodeCleaning.trisovic: {
        ExecutionClass.success: 1472,
        ExecutionClass.failure: 2223,
        ExecutionClass.timed_out: 3719,
        ExecutionClass.unknown: 0,
    },
    CodeCleaning.trisovic_or_none: {
        ExecutionClass.success: 1581,
        ExecutionClass.failure: 1238,
        ExecutionClass.timed_out: 5790,
        ExecutionClass.unknown: 0,
    },
}

def translate(obj: CodeCleaning | Work | ExecutionClass, extra: None | str = None) -> str:
    translation_dict: Mapping[tuple[Any, Any], str] = {
        (Work, Work.original_work): "Original work",
        (Work, Work.this_work): "This work",
        (CodeCleaning, CodeCleaning.none): "Unmodified",
        (CodeCleaning, CodeCleaning.trisovic): "Tr repairs",
        (CodeCleaning, CodeCleaning.trisovic_or_none): "Best(Tr, unmod)",
        (CodeCleaning, CodeCleaning.grayson): "Gr repairs",
        (CodeCleaning, CodeCleaning.grayson_packages): "Gr rep+nix",
        (CodeCleaning, CodeCleaning.grayson_packages_order): "Gr rep+nix+order",
        (ExecutionClass, ExecutionClass.success): "Success",
        (ExecutionClass, ExecutionClass.failure): "Failure",
        (ExecutionClass, ExecutionClass.timed_out): "Timed out",
    }
    keys = (type(obj), obj) if extra is None else (extra, obj)
    return translation_dict.get(keys, str(obj))


def percent(num: float, denom: float, plaintext: bool) -> str:
    if plaintext:
        if denom == 0.0:
            return "0/0"
        else:
            return fr"{100 * num / denom:.0f}% = {num}/{denom}"
    else:
        if denom == 0.0:
            return r"\frac{0}/{0}"
        else:
            return fr"\[{100 * num / denom:.0f}\% = \frac{{{num}}}{{{denom}}}\]"


def latex_row(cells: list[str]) -> str:
    return " & ".join(cells) + r" \\"


def plaintext_row(cells: list[str], size: int, header: bool = False, center: bool = False) -> str:
    alignment = "^" if center else "<"
    ret = "| " + " | ".join(f"{cell: {alignment}{size}s}" for cell in cells) + " |"
    if header:
        ret += "\n|-" + "-|-".join(size * "-" for cell in cells) + "-|"
    return ret


def overall_classification_table(
        script_agg_r_version_df: pandas.DataFrame,
) -> str:
    df = script_agg_r_version_df.reset_index()
    data: Mapping[Work, Mapping[CodeCleaning, Mapping[ExecutionClass, int]]] = {
        Work.original_work: orig_work_dict,
        Work.this_work: {
            code_cleaning: {
                execution_class: sum((df["code_cleaning"] == code_cleaning) & (df["execution_class"] == execution_class))
                for execution_class in ExecutionClass
            }
            for code_cleaning in CodeCleaning
        }
    }
    # best_mask = (df["code_cleaning"] == CodeCleaning.none) | (df["code_cleaning"] == CodeCleaning.trisovic)
    # successes = set(df[best_mask & (df["execution_class"] == ExecutionClass.success)]["code"])
    # timed_outs = set(df[best_mask & (df["execution_class"] == ExecutionClass.timed_out)]["code"]) - successes
    # failures = set(df[best_mask & (df["execution_class"] == ExecutionClass.failure)]["code"]) - successes - timed_outs
    # unknowns = set(df[best_mask]["code"]) - successes - timed_outs - failures
    # data[Work.this_work][CodeCleaning.best] = {
    #     ExecutionClass.success: len(successes),
    #     ExecutionClass.timed_out: len(timed_outs),
    #     ExecutionClass.failure: len(failures),
    #     ExecutionClass.unknown: len(unknowns),
    # }
    code_cleanings = [CodeCleaning.none, CodeCleaning.trisovic, CodeCleaning.trisovic_or_none, CodeCleaning.grayson, CodeCleaning.grayson_packages]
    works = [Work.original_work, Work.this_work]
    classes = [ExecutionClass.success, ExecutionClass.failure, ExecutionClass.timed_out]
    size = 15
    work_code_cleanings = [
        (Work.original_work, CodeCleaning.none            ),
        (Work.this_work    , CodeCleaning.none            ),
        (Work.original_work, CodeCleaning.trisovic        ),
        (Work.this_work    , CodeCleaning.trisovic        ),
        # (Work.original_work, CodeCleaning.trisovic_or_none),
        # (Work.this_work    , CodeCleaning.trisovic_or_none),
        (Work.this_work    , CodeCleaning.grayson         ),
        (Work.this_work    , CodeCleaning.grayson_packages),
    ]
    return "\n".join([
        r"\begin{tabular}{rcccccc}",
        latex_row([
            "",
            *[
                fr"{translate(code_cleaning)}"
                for code_cleaning, work in work_code_cleanings
            ],
        ]),
        latex_row([
            "",
            *[translate(work) for code_cleaning, work in work_code_cleanings],
        ]),
        *[
            latex_row([
                translate(class_),
                *[
                    percent(
                        data[work].get(code_cleaning, {}).get(class_, 0),
                        sum(
                            data[work].get(code_cleaning, {}).get(this_class, 0)
                            for this_class in ExecutionClass
                        ),
                        plaintext=False,
                    )
                    for work, code_cleaning in work_code_cleanings
                ]
            ])
            for class_ in classes
        ],
        r"\end{tabular}",
        "",
        plaintext_row([
            "",
            *[translate(code_cleaning) for work, code_cleaning in work_code_cleanings],
        ], size=size),
        plaintext_row([
            "",
            *[
                translate(work)
                for work, code_cleaning in work_code_cleanings
            ]
        ], size=size, header=True),
        *[
            plaintext_row([
                translate(class_),
                *[
                    percent(
                        data[work].get(code_cleaning, {}).get(class_, 0),
                        sum(
                            data[work].get(code_cleaning, {}).get(this_class, 0)
                            for this_class in ExecutionClass
                        ),
                        plaintext=True,
                    )
                    for work, code_cleaning in work_code_cleanings
                ]
            ], size=size)
            for class_ in classes
        ],
    ])


def r_version_table(
        script_agg_iterations_df: pandas.DataFrame,
        code_cleaning: CodeCleaning
) -> str:
    df = script_agg_iterations_df[script_agg_iterations_df.code_cleaning == code_cleaining]
    r_versions = df.r_versions.unique(sort=True)
    return "\n".join([
        plaintext_row("R version", "working %"),
        *[
            plaintext_row([
                r_version,
                percent(
                    sum(df[df.r_version == r_version].execution_class == ExecutionClass.success),
                    sum(df.r_version == r_version),
                    plaintext=True,
                ),
            ])
            for r_version in r_versions
        ],
    ])


@functools.cache
def get_orig_data(
        condition: TrisovicCondition,
) -> Mapping[DataverseDataset, Mapping[str, str]]:
    url_prefix = "https://raw.githubusercontent.com/atrisovic/dataverse-r-study/master"
    r_version_str = "".join(condition.r_version.split(".")[:2])
    env_cleaning_str = "" if condition.code_cleaning else "no_"
    request = requests.get(f"{url_prefix}/analysis/data/r{r_version_str}_{env_cleaning_str}env.csv")
    ret: Mapping[DataverseDataset, dict[str, str]] = collections.defaultdict(dict)
    for row in csv.reader(request.text.split("\n"), delimiter="\t"):
        ret[DataverseDataset(row[0])][row[1]] = row[2]
    return ret


def compare_with_orig(
        code_condition_result_map: Mapping[DataverseDataset, Mapping[TrisovicCondition, list[MyReducedResult]]]
) -> None:
    raise NotImplementedError


def status_update(
        experimental_config: Config,
        doi_df: pandas.DataFrame,
        script_df: pandas.DataFrame,
        complete: bool,
) -> None:
    print("#" * 80)
    print(f"{len(doi_df)} dois, {len(script_df)} scripts")

    doi_df["experimental_status"] = doi_df.result.map(get_experimental_status)
    normal_mask = doi_df.experimental_status == "normal"
    if not all(normal_mask):
        print(
            "experimental_status",
            list(doi_df.experimental_status.value_counts().items()),
        )
        for _, row in doi_df[doi_df["experimental_status"] == "exception in runner"].iterrows():
            print(row["code"], "exception:")
            print(traceback.print_exception(row["result"], file=sys.stderr))

    script_df["execution_class"] = script_df["result"].map(lambda obj: obj.execution_class)
    print(
        "execution_class",
        list(script_df["execution_class"].value_counts().items()),
    )

    script_agg_iterations_df = pandas.DataFrame()
    script_agg_iterations_df["n_observations"] = [] if script_df.empty else (
        script_df
        .groupby(["r_version", "code_cleaning", "code", "script"], sort=False)
        .apply(lambda group: len(group))
    )

    script_agg_iterations_df["complete"] = script_agg_iterations_df.n_observations == experimental_config.n_repetitions
    if complete and not all(script_agg_iterations_df.complete):
        incompletes = script_agg_iterations_df[~script_agg_iterations_df.complete]
        for index, _ in incompletes.iterrows():
            print(index, "have only", script_agg_iterations_df.loc[index, "n_observations"], "observations!")

    script_agg_iterations_df["deterministic"] = [] if script_df.empty else (
        script_df
        .groupby(["r_version", "code_cleaning", "code", "script"], sort=False)
        .apply(
            lambda group:
            (
                group["result"]
                .apply(lambda result: (
                    result.exit_code,
                    "\n".join(result.stdout.split("\n")[-5:]),
                    "\n".join(result.stderr.split("\n")[-5:]),
                ))
                .nunique()
            ) == 1
        )
    )
    print(
        "deterministim?",
        list(script_agg_iterations_df["deterministic"].value_counts().items()),
    )

    script_agg_iterations_df["execution_class"] = [] if script_df.empty else (
        script_df
        .groupby(["r_version", "code_cleaning", "code", "script"], sort=False)
        .apply(
            lambda condition_code_script_df:
            ExecutionClass.success if (condition_code_script_df["execution_class"] == ExecutionClass.success).any() else
            ExecutionClass.timed_out if (condition_code_script_df["execution_class"] == ExecutionClass.timed_out).any() else
            ExecutionClass.failure if (condition_code_script_df["execution_class"] == ExecutionClass.failure).any() else
            ExecutionClass.unknown
        )
    )

    script_agg_r_version_df = pandas.DataFrame()
    script_agg_r_version_df["execution_class"] = [] if script_agg_iterations_df.empty else (
        script_agg_iterations_df
        .reset_index()
        .groupby(["code_cleaning", "code", "script"], sort=False)  # NOT r_version
        .apply(
            lambda condition_code_script_df:
            ExecutionClass.success if (condition_code_script_df["execution_class"] == ExecutionClass.success).any() else
            ExecutionClass.timed_out if (condition_code_script_df["execution_class"] == ExecutionClass.timed_out).any() else
            ExecutionClass.failure if (condition_code_script_df["execution_class"] == ExecutionClass.failure).any() else
            ExecutionClass.unknown
        )
    )
    print(overall_classification_table(script_agg_r_version_df))

    latest_r_version = max(script_df["r_version"])
    sub_df = (
        script_df
        [(script_df.execution_class == ExecutionClass.failure) & (script_df.r_version == latest_r_version) & ((script_df.code_cleaning == CodeCleaning.grayson) | (script_df.code_cleaning == CodeCleaning.trisovic))]
        .drop_duplicates(["code_cleaning", "code", "script"])
        [["code_cleaning", "code", "script", "r_version", "result", "doi_idx"]]
    )
    ret = []
    for _, row in sub_df.iterrows():
        if row.result.events and row.result.events[-1].kind == "r_error" and row.result.events[-1].params.get("subkind", None) in {"cannot open the connection", "no such function"}:
            continue
        workflow_execution = doi_df[(doi_df.code == row.code) & (doi_df.r_version == row.r_version) & (doi_df.code_cleaning == row.code_cleaning)].iloc[0]
        ret.append(f"""
- doi: {row.code.persistent_id}
  script: {row.script}
  code_cleaning: {row.code_cleaning}
  exit_code: {row.result.exit_code}
  stderr: |
    {textwrap.indent(shorten_lines(row.result.stderr.strip(), 10, 50), prefix="    ")}
  stdout: |
    {textwrap.indent(shorten_lines(row.result.stdout.strip(), 10, 50), prefix="    ")}
  init_stdout: |
    {textwrap.indent(shorten_lines(doi_df[doi_df.idx == row.doi_idx].iloc[0].result.workflow_execution.procs[0].stdout_b.decode().strip(), 10, 50), prefix="    ")}
  init_stderr: |b
    {textwrap.indent(shorten_lines(doi_df[doi_df.idx == row.doi_idx].iloc[0].result.workflow_execution.procs[0].stderr_b.decode().strip(), 10, 50), prefix="    ")}
""".lstrip())
        if row.result.events:
            ret.append("  events:")
        else:
            ret.append("  no_events: \"Hmm. This is worth investigating.\"")
        for event in row.result.events:
            if event.kind in {"r_error", "r_warning"}:
                ret.append(f"  - kind: {event.kind}")
                for key, val in event.params.items():
                    if val is not None:
                        ret.append(f"      {key}: {val}")
        ret.append("")
    pathlib.Path("errors.yaml").write_text("\n".join(ret))


def run() -> None:
    dask_client = config.dask_client()
    execute_workflow = ExecuteWorkflow()
    my_reduction = MyReduction()
    experimental_config = Config(
        registries=(DataverseTrisovicFixed(),),
        conditions=tuple(
            TrisovicCondition(
                r_version=r_version,
                code_cleaning=code_cleaning,
                wall_time_limit=datetime.timedelta(hours=1.2),
                per_script_wall_time_limit=datetime.timedelta(hours=0.3),
                mem_limit=4 * 1024**3,
            )
            for r_version in ["4.2.2"] # TODO: "3.2.3", "3.6.0", "4.0.2"
            for code_cleaning in [CodeCleaning.none, CodeCleaning.trisovic, CodeCleaning.grayson] # TODO: test CodeCleaning.grayson_packages, CodeCleaning.grayson_pcakages_order
        ),
        analysis=execute_workflow,
        reduction=my_reduction,
        # TODO: larger sample
        sample_size=10,
        seed=0,
        n_repetitions=1,
        # TODO: more repetitions
    )

    print("Config loaded")

    #all_results = tqdm.tqdm(get_parsed_results(experimental_config))
    # print(f"Got {len(all_results)} results")

    n_results, results_stream = stream_results(
        dask_client,
        experimental_config,
        randomize_dispatch_order=True,
    )
    all_results = tqdm.tqdm(
        results_stream,
        desc="jobs completed",
        total=n_results,
    )
    # all_results = get_results(experimental_config)

    doi_df = pandas.DataFrame(columns=["code", "r_version", "code_cleaning", "result"])
    script_df = pandas.DataFrame(columns=["code", "r_version", "code_cleaning", "script", "result"])

    cleared = 0  # DEBUG
    for n, (code, condition, detailed_result_or_exc) in enumerate(all_results):
        code = expect_type(WorkflowCode, code)
        condition = expect_type(TrisovicCondition, condition)
        doi_df = pandas.concat([
            doi_df,
            pandas.DataFrame.from_records(
                [
                    {
                        "idx": n,
                        "code": code.code,
                        "r_version": condition.r_version,
                        "code_cleaning": condition.code_cleaning,
                        "result": detailed_result_or_exc,
                    }
                ],
            ),
        ])
        # DEBUG
        if any(
                any([
                    b"CMake was not found" in proc.stderr_b,
                    b"charmonium_state.R" in proc.stderr_b,
                    b"cannot find nlopt" in proc.stderr_b,
                    b"awk: command not found" in proc.stderr_b,
                    condition.code_cleaning == CodeCleaning.grayson,
                ])
                for proc in detailed_result_or_exc.workflow_execution.procs
        ):
            clear_cache(reduced_analysis, my_reduction, execute_workflow, code, condition, 0)
            clear_cache(analyze, execute_workflow, code, condition, 0)
            cleared += 1
        print("=====\ncleared:", cleared)  # DEBUG
        if isinstance(detailed_result_or_exc, MyReducedResult):
            script_df = pandas.concat([
                script_df,
                pandas.DataFrame.from_records(
                    [
                        {
                            "doi_idx": n,
                            "code": expect_type(WorkflowCode, code).code,
                            "r_version": condition.r_version,
                            "code_cleaning": condition.code_cleaning,
                            "script": script_name,
                            "result": script_result,
                        }
                        for script_name, script_result in detailed_result_or_exc.script_results.items()
                    ],
                ),
            ])
        try:
            status_update(experimental_config, doi_df, script_df, False)
        except Exception as exc:
            traceback.print_exception(exc, file=sys.stderr)

    try:
        status_update(experimental_config, doi_df, script_df, True)
    except Exception as exc:
        traceback.print_exception(exc, file=sys.stderr)
    import IPython; IPython.embed()  # type: ignore
