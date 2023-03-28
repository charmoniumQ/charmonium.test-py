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


class Condition(abc.ABC):
    pass


class Analysis(abc.ABC):
    @abc.abstractmethod
    def analyze(
            self,
            code: Code,
            condition: Condition,
    ) -> Result: ...


class Result(abc.ABC):
    pass
