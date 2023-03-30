from .r_lang import RLangExecutor
from .generic import WorkflowExecutor as WorkflowExecutor

executors = {
    "R": RLangExecutor(),
}
