import datetime
import shlex
import pathlib
import functools
from typing import Callable, Mapping, Optional, cast

from ...util import fs_escape, expect_type
from ...types import Condition
from ...conditions import TrisovicCondition, CodeCleaning
from .generic import WorkflowExecutor
from .trisovic_code_cleaning import main as trisovic_code_cleaning
from .grayson_code_cleaning import main as grayson_code_cleaning


code_cleaners: Mapping[CodeCleaning, Callable[[pathlib.Path, pathlib.Path, pathlib.Path], None]] = {
    CodeCleaning.trisovic: trisovic_code_cleaning,
    CodeCleaning.none: cast(Callable[[pathlib.Path, pathlib.Path, pathlib.Path], None], lambda _code_dir, _out_dir, _log_dir: None),
    CodeCleaning.grayson_files: functools.partial(grayson_code_cleaning, fix_paths=True, fix_packages=False, fix_order=False),
    CodeCleaning.grayson_files_packages: functools.partial(grayson_code_cleaning, fix_paths=True, fix_packages=True, fix_order=False),
    CodeCleaning.grayson_files_packages_order: functools.partial(grayson_code_cleaning, fix_paths=True, fix_packages=True, fix_order=True),
}


r_runner_images = {
    "4.2.2": "wfregtest.azurecr.io/r-runner-4-2-2:commit-0a5c7863-1683868575",
    "4.0.2": "wfregtest.azurecr.io/r-runner-4-0-2:commit-0a5c7863-1683868575",
    "3.6.0": "wfregtest.azurecr.io/r-runner-3-6-0:commit-0a5c7863-1683868575",
    "3.2.3": "wfregtest.azurecr.io/r-runner-3-2-3:commit-0a5c7863-1683868575",
}


class RLangExecutor(WorkflowExecutor):
    def get_container(
            self,
            code_dir: pathlib.Path,
            out_dir: pathlib.Path,
            log_dir: pathlib.Path,
            cpus: int,
            mem_limit: int,
            condition: Condition,
    ) -> tuple[str, tuple[str, ...]]:
        condition = expect_type(TrisovicCondition, condition)
        code_cleaners[condition.code_cleaning](code_dir, out_dir, log_dir)
        r_files = sorted([*code_dir.glob("**/*.R"), *code_dir.glob("**/*.r")])
        script_path = (log_dir / "charmonium_test_py.sh").resolve()
        script_lines = [
            "#!/bin/sh",
            "set +e -x",
        ]
        index_lines = []
        max_timeout = int(condition.per_script_wall_time_limit.total_seconds())
        for r_file in r_files:
            r_file = r_file.relative_to(code_dir)
            r_file_result = out_dir / fs_escape(str(r_file))
            index_lines.append(f"{r_file_result.relative_to(out_dir)} {shlex.quote(str(r_file))}")
            (out_dir / r_file_result).mkdir()
            script_lines.extend([
                f"cd {code_dir}",
                f"timeout -k 30 {max_timeout} Rscript {shlex.quote(str(r_file))} > {r_file_result}/stdout 2> {r_file_result}/stderr",
                f"echo -e $? > {r_file_result}/status",
                "",
            ])
        (out_dir / "index").write_text("\n".join(index_lines))
        script_path.write_text("\n".join(script_lines))
        script_path.chmod(0o755)
        override_script = out_dir / "main_2023_05_11.R"
        return (
            r_runner_images[condition.r_version],
            ("Rscript", "-e", str(override_script)) if override_script.exists() else (str(script_path),),
        )
