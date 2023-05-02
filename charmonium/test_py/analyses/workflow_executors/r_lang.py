import pathlib

from ...util import fs_escape
from ...types import Condition
from .generic import WorkflowExecutor


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
        r_files = sorted([*code_dir.glob("**/*.R"), *code_dir.glob("**/*.r")])
        script_path = (log_dir / "charmonium_test_py.sh").resolve()
        lines = [
            "#!/bin/sh",
            "set +e -x",
            # This one gets echoed into stderr
            "set +e -x",
        ]
        for r_file in r_files:
            r_file = r_file.relative_to(code_dir)
            r_file_result = out_dir / fs_escape(str(r_file))
            lines.extend([
                f"mkdir -p {r_file_result}",
                f"cd {code_dir}",
                f"echo {r_file_result.relative_to(out_dir)} {r_file} >> {out_dir}/index",
                f"Rscript {r_file} > {r_file_result}/stdout 2> {r_file_result}/stderr",
                f"echo -e $? > {r_file_result}/status",
                "",
            ])
        script_path.write_text("\n".join(lines))
        script_path.chmod(0o755)
        return (
            "wfregtest.azurecr.io/r-runner-4_0_4:commit-c9899448-1682966224",
            (str(script_path),),
        )
