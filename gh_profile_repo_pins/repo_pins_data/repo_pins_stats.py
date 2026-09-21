from gh_profile_repo_pins.repo_pins_data.repo_pins_contributor_id import (
    ContributorIdObs,
    ContributorIdResolver,
)
from gh_profile_repo_pins.repo_pins_exceptions import RepoPinStatsError
from subprocess import PIPE, CalledProcessError, CompletedProcess, run
from concurrent.futures import ThreadPoolExecutor, as_completed
import gh_profile_repo_pins.repo_pins_enum as enums
from re import I, Match, Pattern, compile
from dataclasses import dataclass, field
from tempfile import mkdtemp
from shutil import rmtree
from typing import Any
from os import environ

AuthorIdentity = tuple[set[str], set[str]]
CreditableCommit = tuple[list[AuthorIdentity], int, int]


@dataclass(slots=True)
class _Commit:
    hash: str
    tree: str
    parents: list[str]
    authors: list[AuthorIdentity] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    changed_paths: set[str] = field(default_factory=set)


class RepoPinStats:

    __TMP_DIR: str = "tmp_git"
    __IS_CALLED_PROCESS_ERR: bool = True
    __MAX_WORKERS: int = 8

    __COMMIT_LABEL: str = "@@COMMIT@@"
    __AUTHOR_LABEL: str = "@@AUTHOR@@"
    __RAW_AUTHOR_LABEL: str = "@@RAW_AUTHOR@@"
    __CO_AUTHOR_LABEL: str = "Co-authored-by:"

    __COMMIT_REG: Pattern[str] = compile(
        pattern=r"^{}\s+([0-9a-f]+)\s+([0-9a-f]+)(?:\s+([0-9a-f ]+))?\s*$".format(
            __COMMIT_LABEL
        ),
        flags=I,
    )
    __AUTHOR_REG: Pattern[str] = compile(
        pattern=r"^{}\s+(.+?)\s*<([^>]+)>\s*$".format(__AUTHOR_LABEL)
    )
    __RAW_AUTHOR_REG: Pattern[str] = compile(
        pattern=r"^{}\s+(.+?)\s*<([^>]+)>\s*$".format(__RAW_AUTHOR_LABEL)
    )
    __CO_AUTHOR_REG: Pattern[str] = compile(
        pattern=r"^\s*{}\s*(.+?)\s*<([^>]+)>\s*$".format(__CO_AUTHOR_LABEL),
        flags=I,
    )
    __NUMSTAT_REG: Pattern[str] = compile(pattern=r"^\d+\t\d+\t")
    __RAW_DIFF_REG: Pattern[str] = compile(
        pattern=r"^:[0-7]{6}\s+[0-7]{6}\s+[0-9a-f]+\s+[0-9a-f]+\s+([A-Z])[0-9]*\t(.+)$",
        flags=I,
    )

    __REAPPLY_MIN_PATHS: int = 10
    __REAPPLY_PATH_OVERLAP: float | int = 0.8

    def __init__(self, gh_token: str | None = None) -> None:
        self.__gh_token: str | None = gh_token

    def __get_completed_process(self, args: list[str]) -> CompletedProcess[str]:
        env: dict[str, str] = environ.copy()
        for key, value in (
            ("GIT_TERMINAL_PROMPT", "0"),
            ("GIT_OPTIONAL_LOCKS", "0"),
            ("GIT_ASKPASS", "true"),
            ("GIT_PAGER", "cat"),
        ):
            env.setdefault(key, value)

        return run(
            args=args,
            check=self.__IS_CALLED_PROCESS_ERR,
            stdout=PIPE,
            stderr=PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            env=env,
        )

    def __fetch_git_commit_data(self, url: str, tmp_dir: str) -> CompletedProcess[str]:
        self.__get_completed_process(
            args=[
                "git",
                "clone",
                "--no-tags",
                "--single-branch",
                url,
                tmp_dir,
            ]
        )
        return self.__get_completed_process(
            args=[
                "git",
                "-C",
                tmp_dir,
                "-c",
                "i18n.logOutputEncoding=UTF-8",
                "log",
                "HEAD",
                "--use-mailmap",
                "--reverse",
                "--topo-order",
                "--diff-merges=first-parent",
                "--raw",
                "--numstat",
                "--format={} %H %T %P%n{} %aN <%aE>%n{} %an <%ae>%n%B%n".format(
                    self.__COMMIT_LABEL,
                    self.__AUTHOR_LABEL,
                    self.__RAW_AUTHOR_LABEL,
                ),
            ]
        )

    @staticmethod
    def __id_from_match(match: Match[str]) -> AuthorIdentity:
        email: str = match.group(2).lower().strip()
        return {match.group(1).lower().strip()}, ({email} if email else set())

    @staticmethod
    def __append_commit(commits: list[_Commit], commit: _Commit | None) -> None:
        if commit and commit.authors:
            commits.append(commit)

    def __parse_commits(self, output: str) -> list[_Commit]:
        commits: list[_Commit] = []
        commit: _Commit | None = None

        for line in output.splitlines():
            commit_match: Match[str] | None = self.__COMMIT_REG.fullmatch(string=line)
            if commit_match:
                self.__append_commit(commits=commits, commit=commit)
                commit = _Commit(
                    hash=commit_match.group(1),
                    tree=commit_match.group(2),
                    parents=(
                        commit_match.group(3).split() if commit_match.group(3) else []
                    ),
                )
                continue

            if commit is None:
                continue

            author_match: Match[str] | None = self.__AUTHOR_REG.fullmatch(string=line)
            if author_match:
                commit.authors = [self.__id_from_match(match=author_match)]
                continue

            raw_author_match: Match[str] | None = self.__RAW_AUTHOR_REG.fullmatch(
                string=line
            )
            if raw_author_match:
                if commit.authors:
                    raw_name, raw_email = self.__id_from_match(match=raw_author_match)
                    commit.authors[0][0].update(raw_name)
                    commit.authors[0][1].update(raw_email)
                continue

            co_author_match: Match[str] | None = self.__CO_AUTHOR_REG.search(
                string=line
            )
            if co_author_match:
                commit.authors.append(self.__id_from_match(match=co_author_match))
                continue

            if commit.authors and self.__NUMSTAT_REG.match(string=line):
                additions, deletions, _ = line.split(sep="\t", maxsplit=2)
                if additions.isdigit() and deletions.isdigit():
                    commit.additions += int(additions)
                    commit.deletions += int(deletions)
                continue

            raw_diff_match: Match[str] | None = self.__RAW_DIFF_REG.fullmatch(
                string=line
            )
            if commit.authors and raw_diff_match:
                commit.changed_paths.update(raw_diff_match.group(2).split(sep="\t"))

        self.__append_commit(commits=commits, commit=commit)
        return commits

    def __is_reapply_overlap(
        self, changed_paths: set[str], reverted_paths: set[str]
    ) -> bool:
        return (
            bool(reverted_paths)
            and len(changed_paths & reverted_paths) / len(reverted_paths)
            >= self.__REAPPLY_PATH_OVERLAP
        )

    def __find_revert_reapply_commits(self, commits: list[_Commit]) -> set[str]:
        commit_by_hash: dict[str, _Commit] = {commit.hash: commit for commit in commits}
        first_parent_children: dict[str, list[_Commit]] = {}

        for commit in commits:
            if commit.parents:
                first_parent_children.setdefault(commit.parents[0], []).append(commit)

        excluded: set[str] = set()
        for commit in commits:
            if len(commit.parents) != 1:
                continue

            reverted_commit: _Commit | None = commit_by_hash.get(commit.parents[0])
            if not reverted_commit or not reverted_commit.parents:
                continue

            pre_revert_commit: _Commit | None = commit_by_hash.get(
                reverted_commit.parents[0]
            )
            if not pre_revert_commit or commit.tree != pre_revert_commit.tree:
                continue

            reverted_paths: set[str] = reverted_commit.changed_paths
            if len(
                reverted_paths
            ) < self.__REAPPLY_MIN_PATHS or not self.__is_reapply_overlap(
                changed_paths=commit.changed_paths, reverted_paths=reverted_paths
            ):
                continue

            for child in first_parent_children.get(commit.hash, []):
                if self.__is_reapply_overlap(
                    changed_paths=child.changed_paths, reverted_paths=reverted_paths
                ):
                    excluded.update((commit.hash, child.hash))

        return excluded

    @staticmethod
    def __creditable_commits(
        commits: list[_Commit], revert_reapply_commits: set[str]
    ) -> list[CreditableCommit]:
        line_count_by_commit: dict[str, int] = {}
        pending_reset_by_commit: dict[str, bool] = {}
        creditable: list[CreditableCommit] = []

        for commit in commits:
            first_parent: str | None = commit.parents[0] if commit.parents else None
            parent_line_count: int = (
                line_count_by_commit.get(first_parent, 0) if first_parent else 0
            )
            line_count_after: int = max(
                0,
                parent_line_count + commit.additions - commit.deletions,
            )
            line_count_by_commit[commit.hash] = line_count_after

            is_inherited_reset: bool = (
                pending_reset_by_commit.get(first_parent, False)
                if first_parent
                else False
            )
            is_full_reset: bool = 0 < parent_line_count <= commit.deletions
            pending_reset_by_commit[commit.hash] = line_count_after == 0 and (
                is_inherited_reset or is_full_reset
            )

            is_excluded: bool = (
                is_full_reset
                or (
                    is_inherited_reset
                    and parent_line_count == 0
                    and commit.additions > 0
                )
                or commit.hash in revert_reapply_commits
            )
            creditable.append(
                (
                    commit.authors,
                    (
                        0
                        if len(commit.parents) > 1 or is_excluded
                        else commit.additions + commit.deletions
                    ),
                    0 if is_excluded else 1,
                )
            )

        return creditable

    @staticmethod
    def __resolve_contributors(
        creditable_commits: list[CreditableCommit],
    ) -> tuple[
        dict[int, set[str]],
        dict[int, set[str]],
        dict[int, float | int],
        dict[int, int],
    ]:
        id_idx: dict[tuple[frozenset[str], frozenset[str]], int] = {}
        obs: list[ContributorIdObs] = []

        def id_node(names: set[str], emails: set[str]) -> int:
            key: tuple[frozenset[str], frozenset[str]] = (
                frozenset[str](names),
                frozenset[str](emails),
            )
            if key not in id_idx:
                id_idx[key] = len(obs)
                obs.append(ContributorIdObs.create(names=names, emails=emails))
            return id_idx[key]

        commit_nodes: list[tuple[list[int], int, int]] = [
            (
                [id_node(names=names, emails=emails) for names, emails in authors],
                changes,
                credit,
            )
            for authors, changes, credit in creditable_commits
        ]

        roots: list[int] = ContributorIdResolver(obs=obs).resolve()

        contributor_authors: dict[int, set[str]] = {}
        contributor_emails: dict[int, set[str]] = {}
        for (authors, emails), idx in id_idx.items():
            root: int = roots[idx]
            contributor_authors.setdefault(root, set()).update(authors)
            contributor_emails.setdefault(root, set()).update(emails)

        contributor_stats: dict[int, float | int] = dict.fromkeys(
            contributor_authors, 0.0
        )
        contributor_commits: dict[int, int] = dict.fromkeys(contributor_authors, 0)

        for nodes, changes, credit in commit_nodes:
            contributor_roots: set[int] = {roots[node] for node in nodes}
            if not contributor_roots:
                continue

            contribution_share: float | int = changes / len(contributor_roots)
            for root in contributor_roots:
                contributor_stats[root] += contribution_share
                contributor_commits[root] += credit

        return (
            contributor_authors,
            contributor_emails,
            contributor_stats,
            contributor_commits,
        )

    def __fetch_repo_stats(self, owner_repo: str) -> list[dict[str, Any]]:
        tmp_dir: str = mkdtemp(prefix=self.__TMP_DIR)

        try:
            commit_data: CompletedProcess[str] = self.__fetch_git_commit_data(
                url=f"https://{f"{self.__gh_token}@" if self.__gh_token else ""}github.com/{owner_repo}.git",
                tmp_dir=tmp_dir,
            )
            if not commit_data.stdout:
                return []
            commits: list[_Commit] = self.__parse_commits(output=commit_data.stdout)
        except CalledProcessError as err:
            raise RepoPinStatsError(
                msg=f"Git process error: {err.stderr.strip() or err.stdout.strip() or err}"
            )
        finally:
            rmtree(path=tmp_dir, ignore_errors=True)

        if not commits:
            return []

        creditable_commits: list[tuple[list[tuple[set[str], set[str]]], int, int]] = (
            self.__creditable_commits(
                commits=commits,
                revert_reapply_commits=self.__find_revert_reapply_commits(
                    commits=commits
                ),
            )
        )
        (
            contributor_authors,
            contributor_emails,
            contributor_stats,
            contributor_commits,
        ) = self.__resolve_contributors(creditable_commits=creditable_commits)

        return [
            {
                enums.RepoPinsResDictKeys.LOGIN.value: max(
                    contributor_authors[root],
                    key=lambda value: (len(value), value),
                ),
                enums.RepoPinsResDictKeys.STATS.value: contributor_stats[root],
                enums.RepoPinsResDictKeys.CONTRIBUTIONS.value: contributor_commits[
                    root
                ],
                enums.RepoPinsResDictKeys.AUTHOR.value: contributor_authors[root],
                enums.RepoPinsResDictKeys.EMAIL.value: contributor_emails[root],
            }
            for root in sorted(
                contributor_authors,
                key=lambda root_i: (
                    -contributor_stats[root_i],
                    max(contributor_authors[root_i]).casefold(),
                ),
            )
        ]

    def fetch_contribution_stats(
        self,
        repo_list: list[dict[str, Any]],
        is_percentage_stats: bool = True,
        raise_errors: bool = True,
    ) -> list[dict[str, Any]]:
        tasks: list[tuple[str, dict[str, Any]]] = []
        for repo in repo_list:
            url_tokens: Any = (
                repo.get(enums.RepoPinsResDictKeys.URL.value, "").strip().split("/")
            )
            repo_name: Any = repo.get(enums.RepoPinsResDictKeys.NAME.value, "").strip()
            if len(url_tokens) >= 2 and repo_name:
                tasks.append((f"{url_tokens[-2].strip()}/{repo_name}", repo))

        if not tasks:
            return repo_list

        with ThreadPoolExecutor(
            max_workers=min(self.__MAX_WORKERS, len(tasks))
        ) as thread_pool:
            contribution_data: dict[Any, dict[str, Any]] = {
                thread_pool.submit(self.__fetch_repo_stats, owner_repo): repo
                for owner_repo, repo in tasks
            }

            for completed in as_completed(fs=contribution_data):
                repo = contribution_data[completed]
                try:
                    local_contributors: Any = completed.result()
                except RepoPinStatsError:
                    if raise_errors:
                        raise
                    local_contributors = []

                repo[enums.RepoPinsResDictKeys.LOCAL_CONTRIBUTORS.value] = (
                    local_contributors
                )
                if is_percentage_stats:
                    repo[enums.RepoPinsResDictKeys.CONTRIBUTION.value] = (
                        local_contributors
                    )

        return repo_list
