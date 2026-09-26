from dataclasses import dataclass
from typing import Sequence
from re import sub

ProfileKey = tuple[str, str]


@dataclass(frozen=True)
class ContributorIdObs:
    names: frozenset[str] = frozenset()
    emails: frozenset[str] = frozenset()
    login: str = ""
    user_id: int | None = None

    @classmethod
    def create(
        cls,
        names: object | None = None,
        emails: object | None = None,
        login: object | None = None,
        user_id: int | None = None,
    ) -> "ContributorIdObs":
        return cls(
            names=frozenset[str](norm_vals(vals=names)),
            emails=frozenset[str](norm_vals(vals=emails)),
            login=norm_val(val=login),
            user_id=user_id,
        )

    @property
    def linked_key(self) -> ProfileKey | None:
        if self.user_id is not None:
            return "user_id", str(self.user_id)
        return ("login", self.login) if self.login else None


class ContributorIdResolver:
    def __init__(
        self,
        obs: Sequence[ContributorIdObs],
        is_mult_profile_merge: bool = False,
    ) -> None:
        self.__obs: list[ContributorIdObs] = list(obs)
        self.__is_mult_profile_merge: bool = is_mult_profile_merge
        self.__parent: list[int] = list(range(len(self.__obs)))
        self.__rank: list[int] = [0] * len(self.__obs)
        self.__linked_profiles: list[set[ProfileKey]] = [
            {key} if (key := item.linked_key) is not None else set()
            for item in self.__obs
        ]

    def find(self, idx: int) -> int:
        while self.__parent[idx] != idx:
            self.__parent[idx] = self.__parent[self.__parent[idx]]
            idx = self.__parent[idx]
        return idx

    def union(
        self,
        lft: int,
        rht: int,
        is_mult_profile_merge: bool = False,
    ) -> bool:
        left_root, right_root = self.find(lft), self.find(rht)
        if left_root == right_root:
            return True

        left_profiles: set[tuple[str, str]] = self.__linked_profiles[left_root]
        right_profiles: set[tuple[str, str]] = self.__linked_profiles[right_root]
        combined_profiles: set[tuple[str, str]] = left_profiles | right_profiles
        if (
            left_profiles
            and right_profiles
            and len(combined_profiles) > 1
            and not is_mult_profile_merge
        ):
            return False

        if self.__rank[left_root] < self.__rank[right_root]:
            left_root, right_root = right_root, left_root
        self.__parent[right_root] = left_root
        self.__linked_profiles[left_root] = combined_profiles
        if self.__rank[left_root] == self.__rank[right_root]:
            self.__rank[left_root] += 1
        return True

    def groups(self) -> dict[int, list[int]]:
        groups: dict[int, list[int]] = {}
        for idx, root in enumerate[int](self.resolve()):
            groups.setdefault(root, []).append(idx)
        return groups

    def __merge_linked_profiles(self) -> None:
        seen: dict[ProfileKey, int] = {}
        for idx, item in enumerate[ContributorIdObs](self.__obs):
            if (profile := item.linked_key) is None:
                continue
            first_idx = seen.setdefault(profile, idx)
            if first_idx != idx:
                self.union(idx, first_idx)

    def __merge_exact_vals(self, attr: str) -> None:
        seen: dict[str, int] = {}
        is_mult_profile_merge: bool = attr == "emails" and self.__is_mult_profile_merge
        for idx, item in enumerate[ContributorIdObs](self.__obs):
            for value in getattr(item, attr):
                first_idx: int = seen.setdefault(value, idx)
                if first_idx != idx:
                    self.union(idx, first_idx, is_mult_profile_merge)

    def __merge_exact_names(self) -> None:
        name_groups: dict[str, list[int]] = {}
        for idx, item in enumerate[ContributorIdObs](self.__obs):
            for name in item.names:
                name_groups.setdefault(name, []).append(idx)

        for idxes in name_groups.values():
            if (
                sum(
                    bool(self.__linked_profiles[root])
                    for root in {self.find(idx) for idx in idxes}
                )
                > 1
            ):
                continue
            for idx in idxes[1:]:
                self.union(idxes[0], idx)

    def __root_names(self) -> dict[int, set[str]]:
        names: dict[int, set[str]] = {}
        for idx, item in enumerate[ContributorIdObs](self.__obs):
            if item.names:
                names.setdefault(self.find(idx), set()).update(item.names)
        return names

    def __merge_name_aliases(self) -> None:
        while True:
            root_names: dict[int, set[str]] = self.__root_names()
            choices: dict[int, int] = {}

            for root, names in root_names.items():
                best_score: float | int = 0.0
                best_roots: list[int] = []
                for other_root, other_names in root_names.items():
                    if other_root == root:
                        continue
                    score: float | int = max(
                        (
                            alias_score(lft=name, rht=other_name)
                            for name in names
                            for other_name in other_names
                        ),
                        default=0.0,
                    )
                    if score > best_score:
                        best_score, best_roots = score, [other_root]
                    elif score > 0 and score == best_score:
                        best_roots.append(other_root)
                if best_score > 0 and len(best_roots) == 1:
                    choices[root] = best_roots[0]

            is_merged: bool = False
            handled: set[tuple[int, int]] = set()
            for root, other_root in choices.items():
                if choices.get(other_root) != root:
                    continue
                left_root, right_root = sorted((self.find(root), self.find(other_root)))
                pair = (left_root, right_root)
                if left_root == right_root or pair in handled:
                    continue
                handled.add(pair)
                is_merged |= self.union(lft=left_root, rht=right_root)

            if not is_merged:
                return

    def resolve(self) -> list[int]:
        if not self.__obs:
            return []
        self.__merge_linked_profiles()
        self.__merge_exact_vals(attr="emails")
        self.__merge_exact_names()
        self.__merge_name_aliases()
        return [self.find(idx=idx) for idx in range(len(self.__obs))]


def norm_val(val: object | None) -> str:
    return str(val or "").strip().casefold()


def norm_vals(vals: object | None) -> set[str]:
    if vals is None:
        return set()
    return {
        normalized
        for val in (
            vals if isinstance(vals, (set, frozenset, list, tuple)) else (vals,)
        )
        if (normalized := norm_val(val))
    }


def name_tokens(val: str) -> frozenset[str]:
    return frozenset[str](
        token
        for token in sub(pattern=r"\w+", repl=" ", string=val.casefold()).split()
        if token
    )


def alias_score(lft: str, rht: str) -> float | int:
    left_tokens, right_tokens = name_tokens(lft), name_tokens(rht)
    if not left_tokens or not right_tokens or left_tokens == right_tokens:
        return 0.0

    if left_tokens < right_tokens:
        shorter, longer = left_tokens, right_tokens
    elif right_tokens < left_tokens:
        shorter, longer = right_tokens, left_tokens
    else:
        return 0.0

    if len(shorter) == 1 and len(next(iter(shorter))) < 5:
        return 0.0
    return len(shorter) / len(longer)
