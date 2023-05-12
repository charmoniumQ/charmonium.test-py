import datetime
import dataclasses

from ..types import Condition


@dataclasses.dataclass(frozen=True)
class WorkflowCondition(Condition):
    mem_limit: int
    wall_time_limit: datetime.timedelta
