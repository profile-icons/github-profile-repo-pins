from typing import Iterable, Sequence, Any
from dataclasses import dataclass
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
        if self.login:
            return "login", self.login
        return None


class ContributorIdResolver:
    def __init__(self, obs: Sequence[ContributorIdObs]) -> None:
        self.__obs: list[ContributorIdObs] = list(obs)
        self.__parent: list[int] = list(range(len(self.__obs)))
        self.__rank: list[int] = [0] * len(self.__obs)
        self.__linked_profiles: list[set[ProfileKey | None]] = [
            ({obs.linked_key} if obs.linked_key is not None else set())
            for obs in self.__obs
        ]

    def find(self, idx: int) -> int:
        while self.__parent[idx] != idx:
            self.__parent[idx] = self.__parent[self.__parent[idx]]
            idx = self.__parent[idx]
        return idx

    def union(self, lft: int, rht: int) -> bool:
        left_root = self.find(idx=lft)
        right_root = self.find(idx=rht)
        if left_root == right_root:
            return True

        combined_profiles: set[tuple[Any, ...] | None] = (
            self.__linked_profiles[left_root] | self.__linked_profiles[right_root]
        )
        if len(combined_profiles) > 1:
            return False

        if self.__rank[left_root] < self.__rank[right_root]:
            left_root, right_root = right_root, left_root
        self.__parent[right_root] = left_root
        self.__linked_profiles[left_root] = combined_profiles
        if self.__rank[left_root] == self.__rank[right_root]:
            self.__rank[left_root] += 1
        return True

    def groups(self) -> dict[int, list[int]]:
        grouped: dict[int, list[int]] = {}
        for idx, root in enumerate[int](self.resolve()):
            grouped.setdefault(root, []).append(idx)
        return grouped

    def __merge_linked_profiles(self) -> None:
        profile_idx: dict[ProfileKey, int] = {}
        for idx, obs in enumerate[ContributorIdObs](self.__obs):
            profile: tuple[Any, ...] | None = obs.linked_key
            if profile is None:
                continue
            existing_profile: int | None = profile_idx.get(profile)
            if existing_profile is not None:
                self.union(lft=idx, rht=existing_profile)
            else:
                profile_idx[profile] = idx

    def __merge_exact_vals(self, attr: str) -> None:
        val_idx: dict[str, int] = {}
        for idx, obs in enumerate[ContributorIdObs](self.__obs):
            for val in getattr(obs, attr):
                existing_val = val_idx.get(val)
                if existing_val is not None:
                    self.union(lft=idx, rht=existing_val)
                else:
                    val_idx[val] = idx

    def __merge_exact_names(self) -> None:
        name_groups: dict[str, list[int]] = {}
        for idx, obs in enumerate[ContributorIdObs](self.__obs):
            for name in obs.names:
                name_groups.setdefault(name, []).append(idx)

        for idxes in name_groups.values():
            if (
                len(
                    set().union(
                        *(
                            self.__linked_profiles[root]
                            for root in {self.find(idx=idx) for idx in idxes}
                        )
                    )
                )
                > 1
            ):
                continue
            for idx in idxes[1:]:
                self.union(lft=idxes[0], rht=idx)

    def __root_names(self) -> dict[int, set[str]]:
        root_names: dict[int, set[str]] = {}
        for idx, obs in enumerate[ContributorIdObs](self.__obs):
            if obs.names:
                root_names.setdefault(self.find(idx=idx), set()).update(obs.names)
        return root_names

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
                            alias_score(name, other_name)
                            for name in names
                            for other_name in other_names
                        ),
                        default=0.0,
                    )
                    if score > best_score:
                        best_score = score
                        best_roots = [other_root]
                    elif score > 0 and score == best_score:
                        best_roots.append(other_root)
                if best_score > 0 and len(set[int](best_roots)) == 1:
                    choices[root] = best_roots[0]

            is_merged_any: bool = False
            handled: set[tuple[int, ...]] = set()
            for root, other_root in choices.items():
                if choices.get(other_root) != root:
                    continue
                pair: tuple[int, ...] = tuple(
                    sorted((self.find(idx=root), self.find(idx=other_root)))
                )
                if pair[0] == pair[1] or pair in handled:
                    continue
                handled.add(pair)
                if self.union(lft=pair[0], rht=pair[1]):
                    is_merged_any = True
            if not is_merged_any:
                return

    def resolve(self) -> list[int]:
        if not self.__obs:
            return []
        self.__merge_linked_profiles()
        self.__merge_exact_vals(attr="emails")
        self.__merge_exact_names()
        self.__merge_name_aliases()
        return [self.find(idx=i) for i in range(len(self.__obs))]


def norm_val(val: object | None) -> str:
    return str(val or "").strip().casefold()


def norm_vals(vals: object | None) -> set[str]:
    if vals is None:
        return set()
    iterable: Iterable[object]
    if isinstance(vals, (set, frozenset, list, tuple)):
        iterable = vals
    else:
        iterable = (vals,)
    return {norm for val in iterable if (norm := norm_val(val=val))}


def name_tokens(val: str) -> frozenset[str]:
    return frozenset[str](
        token
        for token in sub(pattern=r"\w+", repl=" ", string=val.casefold()).split()
        if token
    )


def alias_score(lft: str, rht: str) -> float | int:
    left_tokens: frozenset[str] = name_tokens(val=lft)
    right_tokens: frozenset[str] = name_tokens(val=rht)
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
