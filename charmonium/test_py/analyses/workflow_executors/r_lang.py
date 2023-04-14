import pathlib
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
        r_files = list(code_dir.glob("**/*.R")) + list(code_dir.glob("**/*.r"))
        script = " && ".join(f"Rscript {r_file}" for r_file in r_files)
        return (
            "wfregtest.azurecr.io/r-runner:",
            ("Rscript", "/exec_r_files.R", str(code_dir)),
        )

    # def get_result(
    #         self,
    #         code_dir: pathlib.Path,
    #         out_dir: pathlib.Path,
    #         log_dir: pathlib.Path,
    #         condition: Condition,
    # ) -> Any:
    #     files = {}
    #     # Move stuff to code_dir
    #     for file_obj_json in (code_dir / "metrics.txt").read_text().split("\n"):
    #         file_obj = json.loads(file_obj_json)
    #         files["filename"] = file_obj
    #     with (code_dir / "run_log.csv").open() as f:
    #         for dir, file, error in csv.reader(f):
    #             files[file]["error"] = error
    #     return files
