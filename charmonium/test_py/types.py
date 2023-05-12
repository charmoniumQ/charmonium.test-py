from __future__ import annotations
import abc
import dataclasses
import pathlib
from typing import Iterable, Mapping, Optional


class Registry(abc.ABC):
    @abc.abstractmethod
    def get_codes(self) -> Iterable[Code]: ...


class Code(abc.ABC):
    @abc.abstractmethod
    def checkout(self, path: pathlib.Path) -> None: ...

    # TODO: checkout_command for debugging
    # @abc.abstractmethod
    # def checkout_command(self) -> tuple[str, ...]: ...


class Condition(abc.ABC):
    pass


class Analysis(abc.ABC):
    @abc.abstractmethod
    def analyze(
            self,
            code: Code,
            condition: Condition,
            code_path: pathlib.Path,
    ) -> Result: ...


class Result(abc.ABC):
    pass


class Reduction(abc.ABC):
    @abc.abstractmethod
    def reduce(
            self,
            code: Code,
            condition: Condition,
            result: Result
    ) -> ReducedResult: ...


class ReducedResult(abc.ABC):
    pass
