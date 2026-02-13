from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Article:
    journal: str = ""
    year: str = ""
    issue: str = ""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    institutions: list[str] = field(default_factory=list)
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    funds: list[str] = field(default_factory=list)
    clc_code: str = ""
    url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JournalInfo:
    name: str
    url: str
    pykm: str = ""