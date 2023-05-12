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

import toolz
import charmonium.cache
import tqdm

from .main import  stream_results, get_results, Config, get_codes
from .registries import DataverseTrisovicFixed
from .conditions import TrisovicCondition, CodeCleaning
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
            return ExecutionClass.timed_out
        else:
            return ExecutionClass.failure


@dataclasses.dataclass(frozen=True)
class MyReducedResult(ReducedResult):
    workflow_execution: WorkflowExecution
    script_results: Mapping[str, ScriptResult]
    warnings: tuple[str, ...]


class MyReduction(Reduction):
    def reduce(self, code: Code, condition: Condition, result: Result) -> MyReducedResult:
        if isinstance(result, WorkflowExecution):
            warnings = []
            script_results: dict[str, ScriptResult] = {}
            results_file = result.outputs.files.get(pathlib.Path("index"), None)
            if results_file is not None and (contents := results_file.contents) is not None:
                for line in filter(bool, contents.decode().strip().split("\n")):
                    results_str, _space, r_file = line.partition(" ")
                    results_path = pathlib.Path(results_str)
                    expected_files = {results_path / "status", results_path / "stdout", results_path / "stderr"}
                    if any(expected_file not in result.outputs.files for expected_file in expected_files):
                        warnings.append(f"{expected_files - set(result.outputs.files)} not present")
                        continue
                    status = int(expect_type(bytes, result.outputs.files[results_path / "status"].contents).decode())
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
                    **dataclasses.asdict(result),
                    "logs": result.logs.truncate(2048),
                    "outputs": result.outputs.truncate(2048),
                }),
                script_results=script_results,
                warnings=tuple(warnings),
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
        name: str,
        result: MyReducedResult | Exception,
        experimental_status_by_doi: collections.Counter[str],
        experimental_status_by_script: collections.Counter[str],
) -> None:
    with open("error_details.txt", "a") as fobj:
        if isinstance(result, MyReducedResult):
            # TODO: Fix this if True
            if True: #result.workflow_execution.proc.exit_code == 0:
                any_missing_files = False
                any_failures = False
                all_successes = True
                any_files = False
                for r_file, script_result in result.script_results.items():
                    any_files = True
                    if script_result.status != 0:
                        any_failures = True
                        all_successes = False
                        experimental_status_by_script["failure"] += 1
                        print(f"{name} script failed {r_file}", file=fobj)
                        print(f"  status: {script_result.status}", file=fobj)
                        print("  stderr:", file=fobj)
                        print(textwrap.indent(script_result.stderr, " " * 4), file=fobj)
                        print("  stdout:", file=fobj)
                        print(textwrap.indent(script_result.stdout, " " * 4), file=fobj)
                    else:
                        experimental_status_by_script["successes"] += 1
                        pass
                if not any_files:
                    experimental_status_by_doi["no R scripts"] += 1
                elif any_missing_files:
                    experimental_status_by_doi["missing files"] += 1
                elif any_failures:
                    experimental_status_by_doi["all normal; some scripts fail"] += 1
                elif all_successes:
                    experimental_status_by_doi["all scripts succeed"] += 1
                else:
                    raise RuntimeError("Exhausted cases")
            else:
                experimental_status_by_doi["docker command failed"] += 1
                print(f"{name} docker command failed", file=fobj)
                print_result(result.workflow_execution, file=fobj)
        elif isinstance(result, HashMismatchError):
            experimental_status_by_doi["hash mismatch"] += 1
            print(f"{name} hash_mismatch:", file=fobj)
            print(textwrap.indent(str(result), prefix=" " * 4), sep="\n", file=fobj)
        elif isinstance(result, Exception):
            experimental_status_by_doi["exception in runner"] += 1
            print(f"{name} exception {result.__class__.__name__}")
            print(textwrap.indent("\n".join(traceback.format_exception(result)), prefix=" " * 4))
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


def get_overall_classification(
    code_condition_result_map: Mapping[DataverseDataset, Mapping[TrisovicCondition, list[MyReducedResult]]],
) -> Mapping[Work, Mapping[CodeCleaning, Mapping[ExecutionClass, int]]]:
    class_counts = {
        Work.original_work: {
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
        },
        Work.this_work: {
            CodeCleaning.none: {
                ExecutionClass.success: 0,
                ExecutionClass.failure: 0,
                ExecutionClass.timed_out: 0,
                ExecutionClass.unknown: 0,
            },
            CodeCleaning.trisovic: {
                ExecutionClass.success: 0,
                ExecutionClass.failure: 0,
                ExecutionClass.timed_out: 0,
                ExecutionClass.unknown: 0,
            },
            CodeCleaning.trisovic_or_none: {
                ExecutionClass.success: 0,
                ExecutionClass.failure: 0,
                ExecutionClass.timed_out: 0,
                ExecutionClass.unknown: 0,
            },
        },
    }
    success_any_cleaning = set[tuple[Code, str]]()
    timeout_any_cleaning = set[tuple[Code, str]]()
    failure_any_cleaning = set[tuple[Code, str]]()
    unknown_any_cleaning = set[tuple[Code, str]]()
    for code_cleaning in [CodeCleaning.trisovic, CodeCleaning.none]:
        for code, condition_result_map in code_condition_result_map.items():
            relevant_results = flatten1([
                results
                for condition, results in condition_result_map.items()
                if condition.code_cleaning == code_cleaning
            ])
            scripts = set(flatten1(result.script_results.keys() for results in condition_result_map.values() for result in results))
            for script in scripts:
                if any(result.script_results[script].execution_class == ExecutionClass.success for result in relevant_results):
                    class_counts[Work.this_work][code_cleaning][ExecutionClass.success] += 1
                    success_any_cleaning.add((code, script))
                elif any(result.script_results[script].execution_class == ExecutionClass.timed_out for result in relevant_results):
                    class_counts[Work.this_work][code_cleaning][ExecutionClass.timed_out] += 1
                    timeout_any_cleaning.add((code, script))
                elif relevant_results:
                    class_counts[Work.this_work][code_cleaning][ExecutionClass.failure] += 1
                    failure_any_cleaning.add((code, script))
                else:
                    class_counts[Work.this_work][code_cleaning][ExecutionClass.unknown] += 1
                    unknown_any_cleaning.add((code, script))
    class_counts[Work.this_work][CodeCleaning.trisovic_or_none][ExecutionClass.success] = len(success_any_cleaning)
    class_counts[Work.this_work][CodeCleaning.trisovic_or_none][ExecutionClass.timed_out] = len(timeout_any_cleaning - success_any_cleaning)
    class_counts[Work.this_work][CodeCleaning.trisovic_or_none][ExecutionClass.failure] = len(failure_any_cleaning - timeout_any_cleaning - success_any_cleaning)
    class_counts[Work.this_work][CodeCleaning.trisovic_or_none][ExecutionClass.unknown] = len(unknown_any_cleaning - failure_any_cleaning - timeout_any_cleaning - success_any_cleaning)
    return class_counts


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
    for code, condition_result_map in code_condition_result_map.items():
        if len(condition_result_map) != len(experimental_config.conditions):
            missing = len(set(experimental_config.conditions) - condition_result_map.keys())
            print(f"{code.persistent_id} is missing {missing} conditions", file=file)
        for condition, detailed_results in condition_result_map.items():
            if len(detailed_results) != experimental_config.n_repetitions:
                print(f"{code.persistent_id} {condition} is missing repetition", file=file)

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
                for val, example_dois in val_counter.items():
                    if val is not None and val.strip() and len(example_dois) >= 2:
                        print(f"    {len(example_dois)} {val.strip()[:100] if val is not None else ''}", file=file)
                        for code, scripts in example_dois.items():
                            print(f"      {code.persistent_id}: {', '.join(scripts)}", file=file)

    classification_map = get_overall_classification(code_condition_result_map)
    print(overall_classification_table(classification_map), file=file)

    for code, condition_result_map in code_condition_result_map.items():
        for condition, detailed_results in condition_result_map.items():
            for detailed_result in detailed_results:
                for warning in detailed_result.warnings:
                    print(f"Warning: {warning}", file=file)


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
            for r_version in ["4.0.2", "4.2.2"] # "3.2.3", "3.6.0", "4.0.2"
            for code_cleaning in [CodeCleaning.none, CodeCleaning.trisovic]
        ),
        analysis=ExecuteWorkflow(),
        reduction=MyReduction(),
        sample_size=100,
        seed=0,
        n_repetitions=1,
    )

    print("Config loaded")

    #all_results = tqdm.tqdm(get_parsed_results(experimental_config))
    # print(f"Got {len(all_results)} results")

    n_results, results_stream = stream_results(dask_client, experimental_config)
    all_results = tqdm.tqdm(
        results_stream,
        desc="jobs completed",
        total=n_results,
    )

    code_condition_result_map: dict[DataverseDataset, dict[TrisovicCondition, list[MyReducedResult]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    experimental_status_by_doi = collections.Counter[str]()
    experimental_status_by_script = collections.Counter[str]()

    for n, (code, condition, detailed_result_or_exc) in enumerate(all_results):
        code = expect_type(DataverseDataset, expect_type(WorkflowCode, code).code)
        condition = expect_type(TrisovicCondition, condition)
        detailed_result_or_exc = expect_type(MyReducedResult | Exception, detailed_result_or_exc)
        get_experimental_status(
            code.persistent_id,
            detailed_result_or_exc,
            experimental_status_by_doi,
            experimental_status_by_script,
        )
        if isinstance(detailed_result_or_exc, MyReducedResult):
            code_condition_result_map[code][condition].append(detailed_result_or_exc)

        if n % 1 == 0:
            with open("errors.txt", "w") as fobj:
                print(experimental_status_by_doi, experimental_status_by_doi.total(), file=fobj)
                print(experimental_status_by_script, experimental_status_by_script.total(), file=fobj)
                reduction2(experimental_config, code_condition_result_map, file=fobj)

    with open("errors.txt", "w") as fobj:
        print(experimental_status_by_doi, experimental_status_by_doi.total(), file=fobj)
        print(experimental_status_by_script, experimental_status_by_script.total(), file=fobj)
        reduction2(experimental_config, code_condition_result_map, file=fobj)
