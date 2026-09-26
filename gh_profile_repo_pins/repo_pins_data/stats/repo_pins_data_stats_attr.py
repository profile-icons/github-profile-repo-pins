from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_models import (
    Commit,
    CreditCommit,
    LineChangeKey,
)
from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_policy import (
    RepoPinStatsPolicy,
)
from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_config import (
    RepoPinStatsConfig,
)
from collections import Counter, defaultdict, deque
from pathlib import PurePosixPath
from hashlib import sha256


class RepoPinStatsAttribution:

    @staticmethod
    def is_ancestor(
        ancs_idx: int,
        desc_idx: int,
        commits: list[Commit],
        commit_idx_by_hash: dict[str, int],
        cache: dict[tuple[int, int], bool],
    ) -> bool:
        if ancs_idx == desc_idx:
            return True
        if ancs_idx > desc_idx:
            return False

        cache_key: tuple[int, int] = (ancs_idx, desc_idx)
        if cache_key in cache:
            return cache[cache_key]

        stack: list[str] = list(commits[desc_idx].parents)
        seen: set[str] = set()
        while stack:
            commit_hash: str = stack.pop()
            if commit_hash in seen:
                continue
            seen.add(commit_hash)
            idx: int | None = commit_idx_by_hash.get(commit_hash)
            if idx is None:
                continue
            if idx == ancs_idx:
                cache[cache_key] = True
                return True
            if idx < ancs_idx:
                continue
            stack.extend(commits[idx].parents)

        cache[cache_key] = False
        return False

    @staticmethod
    def path_rename_frag(old_path: str, new_path: str) -> tuple[str, str] | None:
        old_name: str = PurePosixPath(old_path).name
        new_name: str = PurePosixPath(new_path).name
        pfx_len: int = 0
        while (
            pfx_len < min(len(old_name), len(new_name))
            and old_name[pfx_len] == new_name[pfx_len]
        ):
            pfx_len += 1

        sfx_len: int = 0
        max_suffix = min(len(old_name) - pfx_len, len(new_name) - pfx_len)
        while sfx_len < max_suffix and old_name[-1 - sfx_len] == new_name[-1 - sfx_len]:
            sfx_len += 1

        old_end: int = len(old_name) - sfx_len if sfx_len else len(old_name)
        new_end: int = len(new_name) - sfx_len if sfx_len else len(new_name)
        old_frag: str = old_name[pfx_len:old_end]
        new_frag: str = new_name[pfx_len:new_end]
        if old_frag == new_frag or len(old_frag) < 3 or len(new_frag) < 3:
            return None
        return old_frag, new_frag

    @classmethod
    def rename_replacements(cls, commit: Commit) -> list[tuple[str, str]]:
        inferred: Counter[tuple[str, str]] = Counter()
        for old_path, new_path in commit.paths_rename.items():
            replacement: tuple[str, str] | None = cls.path_rename_frag(
                old_path=old_path, new_path=new_path
            )
            if replacement is not None:
                inferred[replacement] += 1

        replacements: set[tuple[str, str]] = {
            replacement for replacement, count in inferred.items() if count >= 3
        }
        for old_fragment, new_fragment in tuple[tuple[str, str]](replacements):
            replacements.add((old_fragment.lower(), new_fragment.lower()))
            replacements.add((old_fragment.upper(), new_fragment.upper()))

        return sorted(replacements, key=lambda pair: len(pair[0]), reverse=True)

    @classmethod
    def exclude_mech_refactors(
        cls, commit: Commit
    ) -> tuple[Counter[LineChangeKey], Counter[LineChangeKey]]:
        replacements: list[tuple[str, str]] = cls.rename_replacements(commit=commit)
        if not replacements:
            return Counter(), Counter()

        adds_remain: Counter[LineChangeKey] = Counter[tuple[str, str]](commit.lines_add)
        dels_cancel: Counter[LineChangeKey] = Counter()
        adds_cancel: Counter[LineChangeKey] = Counter()

        for key_del in commit.lines_del:
            path_old, line_del = key_del
            line_mod: str = line_del
            for frag_old, frag_new in replacements:
                line_mod = line_mod.replace(frag_old, frag_new)
            if line_mod == line_del:
                continue

            path_new: str = commit.paths_rename.get(path_old, path_old)
            key_add: tuple[str, str] = (path_new, line_mod)
            if adds_remain[key_add] <= 0:
                continue

            adds_remain[key_add] -= 1
            dels_cancel[key_del] += 1
            adds_cancel[key_add] += 1

        return dels_cancel, adds_cancel

    @classmethod
    def code_line(cls, line: str) -> str:
        return "\x1f".join(
            RepoPinStatsConfig.CODE_TOKEN_REG.findall(string=line.strip())
        )

    @classmethod
    def exclude_code_base_rewrite(
        cls,
        commit: Commit,
        dels: Counter[LineChangeKey],
        adds: Counter[LineChangeKey],
    ) -> tuple[Counter[LineChangeKey], Counter[LineChangeKey]]:
        del_canon: dict[str, deque[LineChangeKey]] = defaultdict[
            str, deque[LineChangeKey]
        ](deque)
        skip_del: Counter[tuple[str, str]] = dels.copy()
        for key in commit.lines_del:
            if skip_del[key] > 0:
                skip_del[key] -= 1
                continue
            canon: str = cls.code_line(line=key[1])
            if len(canon) < 8 or not any(ch.isalnum() for ch in canon):
                continue
            del_canon[canon].append(key)

        cancel_del: Counter[LineChangeKey] = Counter()
        cancel_add: Counter[LineChangeKey] = Counter()
        skip_add: Counter[tuple[str, str]] = adds.copy()
        for key in commit.lines_add:
            if skip_add[key] > 0:
                skip_add[key] -= 1
                continue
            canon = cls.code_line(line=key[1])
            candidates: deque[tuple[str, str]] | None = del_canon.get(canon)
            if not candidates:
                continue
            key_del: tuple[str, str] = candidates.popleft()
            cancel_del[key_del] += 1
            cancel_add[key] += 1
            if not candidates:
                del_canon.pop(canon, None)

        return cancel_del, cancel_add

    @staticmethod
    def patch_sig(commit: Commit) -> str | None:
        if not commit.lines_add and not commit.lines_del:
            return None
        payload: list[str] = []
        payload.extend(f"+\0{path}\0{line}" for path, line in sorted(commit.lines_add))
        payload.extend(f"-\0{path}\0{line}" for path, line in sorted(commit.lines_del))
        return sha256(
            data="\n".join(payload).encode(encoding="utf-8", errors="ignore")
        ).hexdigest()

    @classmethod
    def valid_change_sum(cls, commits: list[Commit]) -> list[tuple[int, int]]:
        dels_pend: dict[LineChangeKey, deque[int]] = defaultdict[
            LineChangeKey, deque[int]
        ](deque)
        dels_cancel: list[int] = [0] * len(commits)
        adds_cancel: list[int] = [0] * len(commits)
        dels_mech: list[Counter[LineChangeKey]] = []
        adds_mech: list[Counter[LineChangeKey]] = []

        for idx, commit in enumerate[Commit](commits):
            dels, adds = cls.exclude_mech_refactors(commit=commit)
            rewrite_del, rewrite_add = cls.exclude_code_base_rewrite(
                commit=commit,
                dels=dels,
                adds=adds,
            )
            dels.update(rewrite_del)
            adds.update(rewrite_add)
            dels_mech.append(dels)
            adds_mech.append(adds)
            dels_cancel[idx] += sum(dels.values())
            adds_cancel[idx] += sum(adds.values())

        commit_idx_by_hash: dict[str, int] = {
            commit.hash: idx for idx, commit in enumerate[Commit](commits)
        }
        ancs_cache: dict[tuple[int, int], bool] = {}

        for commit_idx, commit in enumerate[Commit](commits):
            skip_del: Counter[tuple[str, str]] = dels_mech[commit_idx].copy()
            for key in commit.lines_del:
                if skip_del[key] > 0:
                    skip_del[key] -= 1
                    continue
                dels_pend[key].append(commit_idx)

            skip_add: Counter[tuple[str, str]] = adds_mech[commit_idx].copy()
            for key in commit.lines_add:
                if skip_add[key] > 0:
                    skip_add[key] -= 1
                    continue

                deq_dels = dels_pend.get(key)
                if not deq_dels:
                    continue

                del_commit_idx: int | None = next(
                    (
                        candidate
                        for candidate in reversed(deq_dels)
                        if cls.is_ancestor(
                            ancs_idx=candidate,
                            desc_idx=commit_idx,
                            commits=commits,
                            commit_idx_by_hash=commit_idx_by_hash,
                            cache=ancs_cache,
                        )
                    ),
                    None,
                )
                if del_commit_idx is None:
                    continue

                deq_dels.remove(del_commit_idx)
                dels_cancel[del_commit_idx] += 1
                adds_cancel[commit_idx] += 1
                if not deq_dels:
                    dels_pend.pop(key, None)

        return [
            (
                max(0, commit.sum_add - adds_cancel[idx]),
                max(0, commit.sum_del - dels_cancel[idx]),
            )
            for idx, commit in enumerate[Commit](commits)
        ]

    @classmethod
    def cred_commits(cls, commits: list[Commit]) -> list[CreditCommit]:
        cred: list[CreditCommit] = []
        patch_sigs: set[str] = set()

        for commit, (adds, dels) in zip(commits, cls.valid_change_sum(commits=commits)):
            is_merge: bool = len(commit.parents) > 1
            changes: int = 0 if is_merge else adds
            authors: list[tuple[set[str], set[str]]] = [
                auth_id
                for auth_id in commit.authors
                if not RepoPinStatsPolicy.is_auto_id(auth_id=auth_id)
            ]
            if changes > 0:
                sig: str | None = cls.patch_sig(commit=commit)
                if sig is not None:
                    if sig in patch_sigs:
                        changes = 0
                    else:
                        patch_sigs.add(sig)
            cred.append((authors, changes, 1 if changes > 0 else 0))

        return cred
