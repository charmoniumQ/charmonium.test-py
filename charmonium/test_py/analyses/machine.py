from __future__ import annotations
import dataclasses
import subprocess
import platform
import xml.etree.ElementTree
from typing import Mapping, Any, ClassVar

from ..util import xml_to_tuple


@dataclasses.dataclass(frozen=True)
class Machine:
    short_description: str
    details: Any

    @staticmethod
    def current_machine() -> Machine:
        if Machine._CURRENT_MACHINE is None:
            Machine._CURRENT_MACHINE = Machine(
                short_description="-".join(
                    [
                        platform.node(),
                        platform.platform(),
                    ]
                ),
                details=xml_to_tuple(
                    xml.etree.ElementTree.fromstring(
                        subprocess.run(
                            ["lstopo", "--output-format", "xml"],
                            check=True,
                            capture_output=True,
                            text=True,
                        ).stdout
                    )
                ),
            )
        return Machine._CURRENT_MACHINE

    def __str__(self) -> str:
        return f"{self.__class__.__name__} {self.short_description}"

    _CURRENT_MACHINE: ClassVar[Machine | None] = None
