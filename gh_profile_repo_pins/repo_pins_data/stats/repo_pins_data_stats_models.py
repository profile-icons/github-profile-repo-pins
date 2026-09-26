from dataclasses import dataclass, field

AuthorId = tuple[set[str], set[str]]
CreditCommit = tuple[list[AuthorId], int, int]
LineChangeKey = tuple[str, str]


@dataclass(slots=True, frozen=True)
class MetaDiff:
    old_blob: str | None
    new_blob: str | None
    old_path: str | None
    new_path: str | None


@dataclass(slots=True)
class Commit:
    hash: str
    tree: str
    parents: list[str]
    authors: list[AuthorId] = field(default_factory=list)
    sum_add: int = 0
    sum_del: int = 0
    paths_change: set[str] = field(default_factory=set)
    paths_rename: dict[str, str] = field(default_factory=dict)
    lines_add: list[LineChangeKey] = field(default_factory=list)
    lines_del: list[LineChangeKey] = field(default_factory=list)
    nb_diffs: list[MetaDiff] = field(default_factory=list)
