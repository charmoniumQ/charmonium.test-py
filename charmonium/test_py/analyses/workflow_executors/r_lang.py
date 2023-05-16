import datetime
import shlex
import pathlib
import functools
from typing import Callable, Mapping, Optional, cast

import json
import chardet

from ...util import fs_escape, expect_type
from ...types import Condition
from ...conditions import TrisovicCondition, CodeCleaning
from ..measure_command_execution import CompletedContainer, measure_docker_execution
from .generic import WorkflowExecutor
from .trisovic_code_cleaning import main as trisovic_code_cleaning
from .grayson_code_cleaning import main as grayson_code_cleaning, generate_nix_flake


code_cleaners: Mapping[CodeCleaning, Callable[[pathlib.Path], set[str]]] = {
    CodeCleaning.trisovic: trisovic_code_cleaning,
    CodeCleaning.none: lambda _code_path: set[str](),
    CodeCleaning.grayson: grayson_code_cleaning,
    CodeCleaning.grayson_packages: grayson_code_cleaning,
    CodeCleaning.grayson_packages_order: grayson_code_cleaning,
}


r_runner_images = {
    "4.2.2": "wfregtest.azurecr.io/r-runner-4-2-2:commit-41383f4a-1684204796",
    "4.0.2": "wfregtest.azurecr.io/r-runner-4-0-2:commit-41383f4a-1684204796",
    "3.6.0": "",
    "3.2.3": "",
}


class RLangExecutor(WorkflowExecutor):
    def do_commands(
            self,
            code_dir: pathlib.Path,
            out_dir: pathlib.Path,
            log_dir: pathlib.Path,
            condition: Condition,
    ) -> tuple[CompletedContainer, ...]:
        condition = expect_type(TrisovicCondition, condition)

        r_files = sorted([*code_dir.glob("**/*.R"), *code_dir.glob("**/*.r")])

        r_file_to_result: dict[str, str] = {}
        packages = set()
        for r_file in r_files:
            r_file_result = out_dir / fs_escape(str(r_file.relative_to(code_dir)))
            assert CodeCleaning.grayson_packages in code_cleaners
            packages.update(code_cleaners[condition.code_cleaning](r_file))

            # Note we won't try to re-encode R source here.
            # This encoding can be quite wrong.
            # Instead, we will use it to encode our own source, prepended and appended to the script.
            r_source = r_file.read_bytes()
            encoding = expect_type(str, chardet.detect(r_source).get("encoding", "ascii"))
            state_name = "charmonium_state.RData"
            r_file.write_bytes(
                b"".join([
                    f"load('{state_name}')\n".encode(encoding),
                    r_source,
                    f"save(list = ls(all.names = TRUE), file = '{state_name}', envir = .GlobalEnv)\n".encode(encoding),
                    f"file.copy('{state_name}, '{r_file_result}/{state_name}')\n".encode(encoding),
                ])
            )
            r_file_result.mkdir()
            r_file_to_result[str(r_file.relative_to(code_dir))] = str(r_file_result.relative_to(out_dir))

        (out_dir / "index.json").write_text(json.dumps(r_file_to_result))

        mem_limit = condition.mem_limit
        cpus = 1
        procs: list[CompletedContainer] = []

        nix_command = ("nix", "develop", "--show-trace", "--command") if condition.use_nix else ()
        if condition.use_nix:
            nix_flake = generate_nix_flake(packages, condition.r_version)
            (code_dir / "flake.nix").write_text(nix_flake)
            (out_dir / "flake.nix").write_text(nix_flake)
            proc = measure_docker_execution(
                r_runner_images[condition.r_version],
                ("env", "--chdir", str(code_dir), *nix_command, "true"),
                mem_limit=condition.mem_limit,
                cpus=cpus,
                readwrite_binds=(out_dir.parent, code_dir,),
                # Double wall time limit because git cloning nixpkgs can take a while
                wall_time_limit=condition.per_script_wall_time_limit * 2,
            )
            procs.append(proc)
            (out_dir / "nix").mkdir()
            (out_dir / "nix/stdout").write_bytes(proc.stdout_b)
            (out_dir / "nix/stderr").write_bytes(proc.stderr_b)
            (out_dir / "nix/exit_code").write_text(str(proc.exit_code))
            (out_dir / "nix/command.sh").write_text(proc.docker_command)
            if (code_dir / "flake.lock").exists():
                (out_dir / "nix/flake.lock").write_bytes((code_dir / "flake.lock").read_bytes())
            if proc.exit_code != 0:
                return tuple(procs)
        if condition.code_cleaning in {CodeCleaning.grayson, CodeCleaning.grayson_packages, CodeCleaning.grayson_packages_order}:
            # Still do this when we use Nix packages, because some Nix packages may be broken or missing.
            (code_dir / "charmonium_init.R").write_text("\n".join(
                f"""if (!require("{package}")) {{ try(install.packages("{package}")); require("{package}"); }}"""
                for package in packages
            ))
            # Even if this fails, we still want to try out the script.
            # We could have incorrectly parsed something that isn't really a package.
            # The script might not need the package they install.
            proc = measure_docker_execution(
                r_runner_images[condition.r_version],
                ("env", "--chdir", str(code_dir), "Rscript", "charmonium_init.R"),
                mem_limit=condition.mem_limit,
                cpus=cpus,
                readwrite_binds=(out_dir.parent, code_dir,),
                # Double wall time limit because installing can take a while
                wall_time_limit=condition.per_script_wall_time_limit * 2,
            )
            procs.append(proc)
            (out_dir / "install").mkdir()
            (out_dir / "install/stdout").write_bytes(proc.stdout_b)
            (out_dir / "install/stderr").write_bytes(proc.stderr_b)
            (out_dir / "install/exit_code").write_text(str(proc.exit_code))
            (out_dir / "install/command.sh").write_text(proc.docker_command)
            (out_dir / "install/charmonium_init.R").write_text((code_dir / "charmonium_init.R").read_text())

        failed = r_files
        new_successes = True
        order_file = out_dir / "order.txt"
        order = []

        
        proc = measure_docker_execution(
            r_runner_images[condition.r_version],
            ("env", "--chdir", str(code_dir), *nix_command, "Rscript", "-e", f"save(list = c(), file = '{state_name}', envir = .GlobalEnv)"),
            mem_limit=condition.mem_limit,
            cpus=cpus,
            readwrite_binds=(out_dir.parent, code_dir,),
            wall_time_limit=condition.per_script_wall_time_limit,
        )
        (out_dir / "init").mkdir()
        (out_dir / "init/stdout").write_bytes(proc.stdout_b)
        (out_dir / "init/stderr").write_bytes(proc.stderr_b)
        (out_dir / "init/exit_code").write_text(str(proc.exit_code))
        (out_dir / "init/command.sh").write_text(proc.docker_command)
        if (code_dir / state_name).exists():
            (out_dir / "init" / state_name).write_bytes((code_dir / state_name).read_bytes())
        if proc.exit_code != 0:
            return tuple(procs)

        while new_successes:
            new_failures = []
            new_successes = False
            for r_file in failed:
                r_file_result = out_dir / pathlib.Path(r_file_to_result[str(r_file.relative_to(code_dir))])
                order.append(str(r_file.relative_to(code_dir)))
                proc = measure_docker_execution(
                    r_runner_images[condition.r_version],
                    ("env", "--chdir", str(code_dir), *nix_command, "Rscript", str(r_file)),
                    mem_limit=condition.mem_limit,
                    cpus=cpus,
                    readwrite_binds=(out_dir.parent, code_dir,),
                    wall_time_limit=condition.per_script_wall_time_limit,
                )
                (r_file_result / "stdout").write_bytes(proc.stdout_b)
                (r_file_result / "stderr").write_bytes(proc.stderr_b)
                (r_file_result / "exit_code").write_text(str(proc.exit_code))
                (r_file_result / "name").write_text(str(r_file.relative_to(code_dir)))
                (r_file_result / "command.sh").write_text(proc.docker_command)
                procs.append(proc)
                if proc.exit_code == 0:
                    new_successes = True
                elif proc.exit_code not in {127, 128+9}:
                    # These are the exit_codes that timeout will send.
                    new_failures.append(r_file)
            if not condition.repeat_failures:
                # Never meant to loop in the first place
                break
            failed = new_failures
        (out_dir / "order.list").write_text("\n".join(order))
        return tuple(procs)
