from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_models import (
    AuthorId,
    Commit,
    MetaDiff,
)
from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_policy import (
    RepoPinStatsPolicy,
)
from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_config import (
    RepoPinStatsConfig,
)
from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_git import (
    RepoPinStatsGit,
)
from subprocess import CalledProcessError
from json import JSONDecodeError, loads
from difflib import SequenceMatcher
from typing import Any
from re import Match


class RepoPinStatsParser:

    def __init__(self, git: RepoPinStatsGit) -> None:
        self.__git: RepoPinStatsGit = git

    @staticmethod
    def merge_patch_data(commits: list[Commit], patch_commits: list[Commit]) -> None:
        patch_by_hash: dict[str, Commit] = {
            commit.hash: commit for commit in patch_commits
        }
        for commit in commits:
            patch: Commit | None = patch_by_hash.get(commit.hash)
            if patch is None:
                continue
            commit.sum_add += patch.sum_add
            commit.sum_del += patch.sum_del
            commit.paths_change.update(patch.paths_change)
            commit.paths_rename.update(patch.paths_rename)
            commit.lines_add.extend(patch.lines_add)
            commit.lines_del.extend(patch.lines_del)
            commit.nb_diffs.extend(patch.nb_diffs)

    @staticmethod
    def id_from_match(match: Match[str]) -> AuthorId:
        email: str = match.group(2).lower().strip()
        return {match.group(1).lower().strip()}, ({email} if email else set())

    @staticmethod
    def append_commit(commits: list[Commit], commit: Commit | None) -> None:
        if commit and commit.authors:
            commits.append(commit)

    def parse_commits(self, output: str, repo_dir: str | None = None) -> list[Commit]:
        commits: list[Commit] = []
        commit: Commit | None = None
        diff_old_path: str | None = None
        diff_new_path: str | None = None
        is_hunk: bool = False

        for line in output.splitlines():
            commit_match: Match[str] | None = RepoPinStatsConfig.COMMIT_REG.fullmatch(
                string=line
            )
            if commit_match:
                self.append_commit(commits=commits, commit=commit)
                commit = Commit(
                    hash=commit_match.group(1),
                    tree=commit_match.group(2),
                    parents=(
                        commit_match.group(3).split() if commit_match.group(3) else []
                    ),
                )
                diff_old_path = None
                diff_new_path = None
                is_hunk = False
                continue

            if commit is None:
                continue

            auth_match: Match[str] | None = RepoPinStatsConfig.AUTH_REG.fullmatch(
                string=line
            )
            if auth_match:
                commit.authors = [self.id_from_match(match=auth_match)]
                continue

            raw_auth_match: Match[str] | None = (
                RepoPinStatsConfig.RAW_AUTH_REG.fullmatch(string=line)
            )
            if raw_auth_match:
                if commit.authors:
                    raw_name, raw_email = self.id_from_match(match=raw_auth_match)
                    commit.authors[0][0].update(raw_name)
                    commit.authors[0][1].update(raw_email)
                continue

            co_auth_match: Match[str] | None = RepoPinStatsConfig.CO_AUTH_REG.search(
                string=line
            )
            if co_auth_match:
                commit.authors.append(self.id_from_match(match=co_auth_match))
                continue

            raw_diff_match: Match[str] | None = (
                RepoPinStatsConfig.RAW_DIFF_REG.fullmatch(string=line)
            )
            if commit.authors and raw_diff_match:
                old_blob: str = raw_diff_match.group(1)
                new_blob: str = raw_diff_match.group(2)
                status: str = raw_diff_match.group(3).upper()
                paths: list[str] = raw_diff_match.group(4).split(sep="\t")
                commit.paths_change.update(paths)
                if status == "R" and len(paths) >= 2:
                    commit.paths_rename[paths[0]] = paths[-1]

                old_path: str | None
                new_path: str | None
                if status in {"R", "C"} and len(paths) >= 2:
                    old_path, new_path = paths[0], paths[-1]
                else:
                    old_path = None if status == "A" else paths[-1]
                    new_path = None if status == "D" else paths[-1]

                if RepoPinStatsPolicy.is_nb_path(
                    path=old_path
                ) or RepoPinStatsPolicy.is_nb_path(path=new_path):
                    commit.nb_diffs.append(
                        MetaDiff(
                            old_blob=None if set[str](old_blob) == {"0"} else old_blob,
                            new_blob=None if set[str](new_blob) == {"0"} else new_blob,
                            old_path=old_path,
                            new_path=new_path,
                        )
                    )
                continue

            if line.startswith("diff --git "):
                diff_old_path = None
                diff_new_path = None
                is_hunk = False
                continue

            if not is_hunk and line.startswith("--- "):
                path: str = line[4:].split("\t", maxsplit=1)[0]
                diff_old_path = (
                    None
                    if path == "/dev/null"
                    else path[2:] if path.startswith("a/") else path
                )
                continue

            if not is_hunk and line.startswith("+++ "):
                path = line[4:].split("\t", maxsplit=1)[0]
                diff_new_path = (
                    None
                    if path == "/dev/null"
                    else path[2:] if path.startswith("b/") else path
                )
                continue

            if line.startswith("@@ "):
                is_hunk = True
                continue

            if not is_hunk:
                continue

            if line.startswith("+") and not line.startswith("+++"):
                if diff_new_path is not None and RepoPinStatsPolicy.is_cred_patch_path(
                    path=diff_new_path
                ):
                    commit.lines_add.append((diff_new_path, line[1:]))
                    commit.sum_add += 1
                continue

            if line.startswith("-") and not line.startswith("---"):
                if diff_old_path is not None and RepoPinStatsPolicy.is_cred_patch_path(
                    path=diff_old_path
                ):
                    commit.lines_del.append((diff_old_path, line[1:]))
                    commit.sum_del += 1
                continue

            if line.startswith(r"\ No newline at end of file"):
                continue

        self.append_commit(commits=commits, commit=commit)
        if repo_dir is not None:
            self.populate_nb_changes(commits=commits, repo_dir=repo_dir)
        return commits

    @staticmethod
    def nb_src_lines(raw: str) -> list[str]:
        try:
            nb: dict | Any = loads(s=raw)
        except JSONDecodeError, TypeError:
            return []
        if not isinstance(nb, dict):
            return []

        res: list[str] = []
        cells: list[dict] | Any = nb.get("cells", [])
        if not isinstance(cells, list):
            return res
        for cell in cells:
            if not isinstance(cell, dict):
                continue
            cell_type: str = str(cell.get("cell_type", "cell"))
            src: list[str] | Any = cell.get("source", [])
            if isinstance(src, list):
                chunks: list[str] = [str(i) for i in src]
            else:
                continue
            for chunk in chunks:
                lines: list[str] = chunk.splitlines()
                if not lines and chunk:
                    lines = [chunk]
                res.extend(f"[{cell_type}] {line}" for line in lines)
        return res

    def populate_nb_changes(self, commits: list[Commit], repo_dir: str) -> None:
        blob_cache: dict[str, list[str]] = {}

        def blob_lines(blob: str | None) -> list[str]:
            if blob is None:
                return []
            if blob not in blob_cache:
                try:
                    raw: str = self.__git.get_complete_proc(
                        args=["git", "-C", repo_dir, "cat-file", "-p", blob]
                    ).stdout
                except CalledProcessError:
                    raw = ""
                blob_cache[blob] = self.nb_src_lines(raw=raw)
            return blob_cache[blob]

        for commit in commits:
            for nb_diff in commit.nb_diffs:
                old_lines: list[str] = blob_lines(blob=nb_diff.old_blob)
                new_lines: list[str] = blob_lines(blob=nb_diff.new_blob)
                old_path: str = nb_diff.old_path or nb_diff.new_path or ""
                new_path: str = nb_diff.new_path or nb_diff.old_path or ""
                if not (
                    (bool(old_path) and RepoPinStatsPolicy.is_cred_path(path=old_path))
                    or (
                        bool(new_path)
                        and RepoPinStatsPolicy.is_cred_path(path=new_path)
                    )
                ):
                    continue

                matcher: SequenceMatcher[str] = SequenceMatcher(
                    a=old_lines, b=new_lines, autojunk=False
                )
                for tag, i_a, i_b, j_a, j_b in matcher.get_opcodes():
                    if tag in {"delete", "replace"} and old_path:
                        for src_line in old_lines[i_a:i_b]:
                            commit.lines_del.append((old_path, src_line))
                            commit.sum_del += 1
                    if tag in {"insert", "replace"} and new_path:
                        for src_line in new_lines[j_a:j_b]:
                            commit.lines_add.append((new_path, src_line))
                            commit.sum_add += 1
