"""The tree a pattern parses into. One class per construct, nothing else."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Char:
    ch: str


@dataclass(frozen=True)
class Dot:
    pass


@dataclass(frozen=True)
class Concat:
    left: object
    right: object


@dataclass(frozen=True)
class Alt:
    left: object
    right: object


@dataclass(frozen=True)
class Repeat:
    child: object
    min: int       # 0 for * and ?, 1 for +
    many: bool     # True for * and +, False for ?
