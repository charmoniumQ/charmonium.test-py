from typing import Optional
import datetime
import dataclasses
import enum

from .workflow_condition import WorkflowCondition


class CodeCleaning(enum.Enum):
    none = "none"
    trisovic = "trisovic"
    trisovic_or_none = "trisovic_or_none"
    grayson_files = "grayson_files"
    grayson_files_packages = "grayson_files_packages"
    grayson_files_packages_order = "grayson_files_packages_order"


@dataclasses.dataclass(frozen=True)
class TrisovicCondition(WorkflowCondition):
    r_version: str
    code_cleaning: CodeCleaning
    per_script_wall_time_limit: datetime.timedelta
