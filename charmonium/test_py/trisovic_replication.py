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

import requests
import pandas  # type: ignore
import toolz  # type: ignore
import charmonium.cache
import tqdm

from .main import  stream_results, get_results, Config, get_codes
from .registries import DataverseTrisovicFixed
from .conditions import TrisovicCondition, CodeCleaning
from .analyses.file_bundle import File
from .codes.dataverse_dataset import HashMismatchError
from .codes import WorkflowCode, DataverseDataset
from .analyses import ExecuteWorkflow, WorkflowExecution
from .conditions import TrisovicCondition
from .util import create_temp_dir, flatten1, expect_type, clear_cache, find_last, is_not_none
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
    status: int
    stdout: str
    stderr: str
    events: list[Event]

    @property
    def execution_class(self) -> ExecutionClass:
        if self.status == 0:
            return ExecutionClass.success
        elif self.status in {124, 128 + 9}:
            # See `man timeout`
            # Timeout can exit with 124 or 128+9
            return ExecutionClass.timed_out
        else:
            return ExecutionClass.failure


@dataclasses.dataclass(frozen=True)
class MyReducedResult(ReducedResult):
    workflow_execution: WorkflowExecution
    script_results: Mapping[str, ScriptResult]


class MyReduction(Reduction):
    def reduce(self, code: Code, condition: Condition, result: Result) -> MyReducedResult:
        if isinstance(result, WorkflowExecution):
            script_results: dict[str, ScriptResult] = {}
            results_file = result.outputs.files.get(pathlib.Path("index"), None)
            if results_file is not None and (contents := results_file.contents) is not None:
                for line in filter(bool, contents.decode().strip().split("\n")):
                    results_str, _space, r_file = line.partition(" ")
                    results_path = pathlib.Path(results_str)
                    expected_files = {results_path / "stdout", results_path / "stderr"}
                    if any(expected_file not in result.outputs.files for expected_file in expected_files):
                        continue
                    if (status_file := result.outputs.files.get(results_path / "status", None)) is not None:
                        status = int(expect_type(bytes, status_file.contents).decode())
                    else:
                        status = 137
                    stderr = expect_type(bytes, result.outputs.files[results_path / "stderr"].contents).decode(errors="backslashreplace")
                    stdout = expect_type(bytes, result.outputs.files[results_path / "stdout"].contents).decode(errors="backslashreplace")
                    script_results[r_file] = ScriptResult(
                        status=status,
                        stderr=textwrap.shorten(stderr, 63 * 1024) + stderr[-1024:] if len(stderr) > 64 * 1024 else stderr,
                        stdout=textwrap.shorten(stdout, 63 * 1024) + stdout[-1024:] if len(stdout) > 64 * 1024 else stdout,
                        events=parse_events(stderr),
                    )
            detailed_result = MyReducedResult(
                workflow_execution=WorkflowExecution(**{  # type: ignore
                    **result.__dict__,
                    "logs": result.logs.truncate(2048),
                    "outputs": result.outputs.truncate(2048),
                }),
                script_results=script_results,
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
    for label, std_bytes in [("stdout", result.proc.stdout_b), ("stderr", result.proc.stderr_b)]:
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
            results_file = result.workflow_execution.outputs.files.get(pathlib.Path("index"), None)
            if result.workflow_execution.proc.exit_code == 0 and results_file is not None:
                contents = expect_type(bytes, results_file.contents)
                for line in filter(bool, contents.decode().strip().split("\n")):
                    results_str, _space, r_file = line.partition(" ")
                    results_path = pathlib.Path(results_str)
                    expected_files = {results_path / "status", results_path / "stdout", results_path / "stderr"}
                    missing_files = expected_files - result.workflow_execution.outputs.files.keys()
                    if missing_files:
                        return "missing files"
                any_failures = False
                all_successes = True
                any_files = False
                for r_file, script_result in result.script_results.items():
                    any_files = True
                    if script_result.status != 0:
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
            else:
                return "docker command failed"
        elif isinstance(result, HashMismatchError):
            return "hash mismatch"
        elif isinstance(result, Exception):
            return "exception in runner"
        else:
            raise TypeError(type(result))


def parse_events(error_text: str) -> list[Event]:
    error_regexes = {
        "r_error": re.compile(
            "Error(?: in (?P<loc>.*) )?:\s+(?P<msg>\S.*)\n(?:Calls: (?P<calls>.*)\n)?(?:In addition: (?P<in_addition>.*)\nIn (?P<in_addition_loc>.*) :(?:\n  | )(?P<in_addition_msg>.*)\n)?Execution halted",
            re.MULTILINE,
        ),
        "r_warnings": re.compile(
            "Warning messages:\n(?P<warnings>(?:\d+: In .* :\s+.*\n)*)",
            re.MULTILINE
        ),
        "r_warning": re.compile(
            "^Warning(?: message:)?(?:\s+[Ii]n (?P<loc>.*) )?:\s+(?P<msg>[a-z0-9].*)",
            # Need to exclude "Warning: Fortran ...". R warnings seem always lowercase.
            re.MULTILINE
        ),
        "gcc_fatal_error": re.compile(
            r"(?P<file>.*):(?P<line>\d+):(?P<col>\d+): fatal error: (?P<msg>.*)\n(?P<source>[\s\S]*)\ncompilation terminated",
            re.MULTILINE,
        ),
        "configure_error": re.compile(r"./configure: line (?P<line>\d+): (?P<msg>.*)"),
        "make_error": re.compile(
            r"make: \*\*\* \[(?P<makefile>.+):(?P<line>\d+): (?P<target>.*)\] Error (?P<exit_code>\d+)"
        ),
        "r_warning_count": re.compile("\nThere were (?P<num_warnings>\d+) warnings"),
        "r_other_error": re.compile("ERROR: '(?P<msg>.*)'"),
        "sigkill": re.compile("Killed!"),
        "install_r_package": re.compile("\* installing \*(?P<type>.*)\* package '(?P<package>.*)' ..."),
        "loaded_r_package": re.compile("Loading required package: (?P<package>.*)"),
    }

    r_error_regexes = {
        "could not find function ...": re.compile("could not find function \"(?P<function>.*)\""),
        "there is no package called ...": re.compile("there is no package called '(?P<package>.*)'"),
        "installation of package ... had non-zero exit status": re.compile("installation of package '(?P<package>.*)' had non-zero exit status"),
        "cannot open the connection": re.compile("cannot open the connection"),
        "cannot open compressed file '...', probable reason 'No such file or directory'": re.compile("cannot open compressed file '(?P<file>.*)', probable reason 'No such file or directory'"),
        "package ... is not available (for R version ...)": re.compile(r"package '(?P<package>.*)' is not available \(for R version (?P<r_ver>.*)\)"),
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
                        del params["msg"]
                        break
            events.append((match.start(), Event(error_kind, params)))
    return list(map(toolz.second, sorted(events)))


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


def get_aggregate_execution_class(
        script_df: pandas.DataFrame,
) -> pandas.DataFrame:
    ret = pandas.DataFrame()
    for code_cleaning in CodeCleaning:
        part = (
            script_df[
                script_df
                ["condition"]
                .apply(lambda condition: condition.code_cleaning) == code_cleaning
            ]
            .groupby(["code", "script"])
            .apply(lambda script_group:
                   ExecutionClass.success if (script_group["execution_class"] == ExecutionClass.success).any() else
                   ExecutionClass.timed_out if (script_group["execution_class"] == ExecutionClass.timed_out).any() else
                   ExecutionClass.failure if (script_group["execution_class"] == ExecutionClass.failure).any() else
                   ExecutionClass.unknown
                   )
        )
        part["code_cleaning"] = code_cleaning
        ret = pandas.concat(ret, part)
    return ret


def translate(obj: CodeCleaning | Work | ExecutionClass, extra: None | str = None) -> str:
    translation_dict: Mapping[tuple[Any, Any], str] = {
        (Work, Work.original_work): "Original work",
        (Work, Work.this_work): "This work",
        (CodeCleaning, CodeCleaning.none): "No code cleaning",
        (CodeCleaning, CodeCleaning.trisovic): "Trisovic code cleaning",
        (CodeCleaning, CodeCleaning.trisovic_or_none): "Best of both",
        (ExecutionClass, ExecutionClass.success): "Success",
        (ExecutionClass, ExecutionClass.failure): "Failure",
        (ExecutionClass, ExecutionClass.timed_out): "Timed out",
    }
    return translation_dict[(type(obj), obj) if extra is None else (extra, obj)]


def percent(num: float, denom: float, plaintext: bool) -> str:
    if plaintext:
        if denom == 0.0:
            return "0/0"
        else:
            return fr"{100 * num / denom:.0f}% = {num}/{denom}"
    else:
        if denom == 0.0:
            return "\frac{0}/{0}"
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
    class_map: Mapping[Work, Mapping[CodeCleaning, Mapping[ExecutionClass, int]]],
) -> str:
    code_cleanings = [CodeCleaning.none, CodeCleaning.trisovic, CodeCleaning.trisovic_or_none]
    works = [Work.original_work, Work.this_work]
    classes = [ExecutionClass.success, ExecutionClass.failure, ExecutionClass.timed_out]
    size = 15
    return "\n".join([
        r"\begin{tabular}{rcccccc}",
        latex_row([
            "",
            *[
                fr"\multicolumn{{2}}{{c}}{{{translate(code_cleaning)}}}"
                for code_cleaning in code_cleanings
            ],
        ]),
        latex_row([
            "",
            *[translate(work) for work in works * 3],
        ]),
        *[
            latex_row([
                translate(class_),
                *[
                    percent(
                        class_map[work][code_cleaning][class_],
                        sum(
                            class_map[work][code_cleaning][this_class]
                                for this_class in ExecutionClass
                        ),
                        plaintext=False,
                    )
                        for code_cleaning in code_cleanings
                        for work in works
                ]
            ])
            for class_ in classes
        ],
        r"\end{tabular}",
        "",
        "| " + " " * (size + 1) + plaintext_row([
            translate(code_cleaning)
            for code_cleaning in code_cleanings
        ], size=size * 2 + 3, center=True),
        plaintext_row([
            "",
            *[
                ""
                for code_cleaning in code_cleanings
                for work in works
            ]
        ],size=size),
        plaintext_row([
            "",
            *[translate(work) for work in works * 3],
        ], size=size, header=True),
        *[
            plaintext_row([
                translate(class_),
                *[
                    percent(
                        class_map[work][code_cleaning][class_],
                        sum(
                            class_map[work][code_cleaning][this_class]
                                for this_class in ExecutionClass
                        ),
                        plaintext=True,
                    )
                        for code_cleaning in code_cleanings
                        for work in works
                ]
            ], size=size)
            for class_ in classes
        ],
    ])


def reduction2(
        experimental_config: Config,
        code_condition_result_map: Mapping[DataverseDataset, Mapping[TrisovicCondition, list[MyReducedResult]]],
        file: Optional[IO[str]],
) -> None:
    event_counter = collections.Counter[str]()
    event_subjects: dict[str, dict[str, dict[str, dict[DataverseDataset, list[str]]]]] = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list))))
    for code, condition_result_map in code_condition_result_map.items():
        for condition, detailed_results in condition_result_map.items():
            if condition.r_version == "4.2.2" and condition.code_cleaning == CodeCleaning.trisovic:
                for detailed_result in detailed_results:
                    for script, script_result in detailed_result.script_results.items():
                        for event in script_result.events:
                            event_counter[event.kind] += 1
                            for key, val in event.params.items():
                                event_subjects[event.kind][key][val][code].append(script)

    for event_kind, count in event_counter.most_common():
        if count > 4:
            print(event_kind, count, file=file)
            for key, val_counter in event_subjects[event_kind].items():
                print(f" {key} ", file=file)
                for val, example_dois in sorted(val_counter.items(), key=lambda pair: len(pair[1])):
                    if val is not None and val.strip() and len(example_dois) >= 2:
                        print(f"    {len(example_dois)} {val.strip()[:100] if val is not None else ''}", file=file)
                        for code, scripts in example_dois.items():
                            print(f"      {code.persistent_id}", file=file)


@functools.cache
def get_orig_data(
        condition: TrisovicCondition,
) -> Mapping[DataverseDataset, Mapping[str, str]]:
    url_prefix = "https://raw.githubusercontent.com/atrisovic/dataverse-r-study/master"
    r_version_str = "".join(condition.r_version.split(".")[:2])
    env_cleaning_str = "" if condition.env_cleaning else "no_"
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
) -> None:
    print(f"{len(doi_df)} dois, {len(script_df)} scripts")

    doi_df["experimental_status"] = doi_df["result"].map(get_experimental_status)
    print(doi_df["experimental_status"].value_counts())

    script_df["execution_class"] = script_df["result"].map(lambda obj: obj.execution_class)
    print(script_df["execution_class"].value_counts())

    script_agg_iterations_df = pandas.DataFrame()
    script_agg_iterations_df["n_observations"] = (
        script_df
        .groupby(["r_version", "code_cleaning", "code", "script"], sort=False)
        .apply(
            lambda group:
            len(group)
        )
    )

    misfit_mask = script_agg_iterations_df.n_observations != experimental_config.n_repetitions
    if any(misfit_mask):
        misfits = script_agg_iterations_df[misfit_mask]
        for index, _ in misfits.iterrows():
            print(index, "have only", misfits.loc[index, "n_observations"], "observations!")

    script_agg_iterations_df["deterministic"] = (
        script_df
        .groupby(["r_version", "code_cleaning", "code", "script"], sort=False)
        .apply(
            lambda group:
            (
                group["result"]
                .apply(lambda result: (result.status, result.stdout.split("\n")[-1], result.stderr.split("\n")[-1]))
                .nunique()
            ) == 1
        )
    )
    print("deterministic?", script_agg_iterations_df["deterministic"].value_counts())

    script_agg_r_version_df = pandas.DataFrame()
    script_agg_r_version_df["aggregated_execution_class"] = (
        script_df
        .groupby(["code_cleaning", "code", "script"], sort=False)  # NOT r_version
        .apply(
            lambda condition_code_script_df:
            ExecutionClass.success if (condition_code_script_df["execution_class"] == ExecutionClass.success).any() else
            ExecutionClass.timed_out if (condition_code_script_df["execution_class"] == ExecutionClass.timed_out).any() else
            ExecutionClass.failure if (condition_code_script_df["execution_class"] == ExecutionClass.failure).any() else
            ExecutionClass.unknown
        )
        .to_frame(name="execution_class")
    )
    script_agg_r_version_df["aggregated_execution_class"].value_counts()


def run() -> None:
    dask_client = config.dask_client()
    experimental_config = Config(
        registries=(DataverseTrisovicFixed(),),
        conditions=tuple(
            TrisovicCondition(
                r_version=r_version,
                code_cleaning=code_cleaning,
                wall_time_limit=datetime.timedelta(hours=1.2),
                per_script_wall_time_limit=datetime.timedelta(hours=0.4),
                mem_limit=4 * 1024**3,
            )
            # TODO: more R versions
            for r_version in ["4.0.2", "4.2.2"] # "3.2.3", "3.6.0"
            # TODO: more code cleanings
            for code_cleaning in [CodeCleaning.none, CodeCleaning.trisovic]
        ),
        analysis=ExecuteWorkflow(),
        reduction=MyReduction(),
        sample_size=5,
        seed=0,
        # TODO: more repetitions
        n_repetitions=2,
    )

    print("Config loaded")

    #all_results = tqdm.tqdm(get_parsed_results(experimental_config))
    # print(f"Got {len(all_results)} results")

    # n_results, results_stream = stream_results(
    #     dask_client,
    #     experimental_config,
    #     randomize_dispatch_order=True,
    # )
    # all_results = tqdm.tqdm(
    #     results_stream,
    #     desc="jobs completed",
    #     total=n_results,
    # )
    all_results = get_results(experimental_config)

    doi_df = pandas.DataFrame()
    script_df = pandas.DataFrame()

    for n, (code, condition, detailed_result_or_exc) in enumerate(all_results):
        doi_df = pandas.concat([
            doi_df,
            pandas.DataFrame.from_records(
                [
                    {
                        "code": code.code,
                        "r_version": condition.r_version,
                        "code_cleaning": condition.code_cleaning,
                        "result": detailed_result_or_exc,
                    }
                ],
            ),
        ])
        if isinstance(detailed_result_or_exc, MyReducedResult):
            script_df = pandas.concat([
                script_df,
                pandas.DataFrame.from_records(
                    [
                        {
                            "code": code.code,
                            "r_version": condition.r_version,
                            "code_cleaning": condition.code_cleaning,
                            "script": script_name,
                            "result": script_result,
                        }
                        for script_name, script_result in detailed_result_or_exc.script_results.items()
                    ],
                ),
            ])
        # status_update(doi_df, script_df)

    import IPython; IPython.embed()  # type: ignore
