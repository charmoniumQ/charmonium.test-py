from typing import Callable, TypeVar, Generic
from typing_extensions import ParamSpec

_Params = ParamSpec("Params")
_Return = TypeVar("Return")


class _DaskDelayed(Generic[Return]):
    pass

def delayed(func: Callable[_Params, _Return]) -> Callable[_Params, _DaskDelayed[_Return]]:
    return func

def compute(*elem: DaskDelayed[_Return]) -> tuple[_Return, ...]:
    return elem
