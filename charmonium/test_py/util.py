import random
import string
from pathlib import Path


def random_str(
        length: int,
        alphabet: str = string.ascii_lowercase + string.digits,
) -> str:
    return "".join(random.choice(alphabet) for _ in range(length))


def get_unused_path(prefix: Path) -> Path:
    while True:
        candidate = prefix / random_str(16)
        if not candidate.exists():
            return candidate
