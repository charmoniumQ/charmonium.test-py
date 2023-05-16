from typing import Optional
import datetime
import dataclasses
import enum

from .workflow_condition import WorkflowCondition


class CodeCleaning(enum.Enum):
    none = "none"
    trisovic = "trisovic"
    trisovic_or_none = "trisovic_or_none"
    grayson = "grayson"
    grayson_packages = "grayson_packages"
    grayson_packages_order = "grayson_packages_order"


@dataclasses.dataclass(frozen=True)
class TrisovicCondition(WorkflowCondition):
    r_version: str
    code_cleaning: CodeCleaning
    per_script_wall_time_limit: datetime.timedelta

    @property
    def use_nix(self) -> bool:
        return self.code_cleaning in {CodeCleaning.grayson_packages, CodeCleaning.grayson_packages_order}

    @property
    def repeat_failures(self) -> bool:
        return self.code_cleaning in {CodeCleaning.grayson_packages_order}
