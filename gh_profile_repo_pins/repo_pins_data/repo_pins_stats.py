from gh_profile_repo_pins.repo_pins_data.repo_pins_contributor_id import (
    ContributorIdObs,
    ContributorIdResolver,
)
from gh_profile_repo_pins.repo_pins_exceptions import RepoPinStatsError
from subprocess import run, PIPE, CompletedProcess, CalledProcessError
from concurrent.futures import ThreadPoolExecutor, as_completed
import gh_profile_repo_pins.repo_pins_enum as enums
from re import compile, I, Pattern, Match
from tempfile import mkdtemp
from shutil import rmtree
from os import environ
from typing import Any


class RepoPinStats:

    __TMP_DIR: str = "tmp_git"
    __IS_CALLED_PROCESS_ERR: bool = True
    __MAX_WORKERS: int = 8

    __AUTHOR_LABEL: str = "@@AUTHOR@@"
    __CO_AUTHOR_LABEL: str = "Co-authored-by:"
    __EMAIL_OPEN_BRACKET: str = " <"

    __AUTHOR_REG: Pattern = compile(
        pattern=r"^{}\s+(.+?)\s*<([^>]+)>\s*$".format(__AUTHOR_LABEL)
    )
    __CO_AUTHOR_REG: Pattern = compile(
        pattern=r"^\s*{}\s*(.+?)\s*<([^>]+)>\s*$".format(__CO_AUTHOR_LABEL), flags=I
    )
    __NUMSTAT_REG: Pattern = compile(pattern=r"^\d+\t\d+\t")

    def __init__(self, gh_token: str | None = None) -> None:
        self.__gh_token: str | None = gh_token

    def __get_completed_process(self, args: list[str]) -> CompletedProcess[str]:
        env = environ.copy()
        env.setdefault("GIT_TERMINAL_PROMPT", "0")
        env.setdefault("GIT_OPTIONAL_LOCKS", "0")
        env.setdefault("GIT_ASKPASS", "true")
        env.setdefault("GIT_PAGER", "cat")
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

    def __fetch_git_commit_data(
        self, url: str, tmp_dir: str
    ) -> CompletedProcess[str] | None:
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
                "--no-merges",
                "--numstat",
                "--format={} %aN <%aE>%n%B%n".format(self.__AUTHOR_LABEL),
            ]
        )

    def __format_author_email_str(self, author_str: str) -> tuple[str, str | None]:
        author_email: list[str] = author_str.lower().split(self.__EMAIL_OPEN_BRACKET)
        return author_email[0].strip(), (
            author_email[1].strip().rstrip(">").strip()
            if len(author_email) > 1
            else None
        )

    def __fetch_repo_stats(self, owner_repo: str) -> list[dict[str, Any]]:
        tmp_dir: str = mkdtemp(prefix=self.__TMP_DIR)
        commits: list[tuple[list[tuple[str, str | None]], int]] = []

        try:
            commit_data: CompletedProcess[str] | None = self.__fetch_git_commit_data(
                url=f"https://{f"{self.__gh_token}@" if self.__gh_token else ""}github.com/{owner_repo}.git",
                tmp_dir=tmp_dir,
            )
            if not commit_data or not commit_data.stdout:
                return []

            commit_authors_emails: list[tuple[str, str | None]] = []
            commit_changes: int = 0

            def finish_commit() -> None:
                nonlocal commit_authors_emails, commit_changes
                if commit_authors_emails:
                    commits.append(
                        (
                            list[tuple[str, str | None]](commit_authors_emails),
                            commit_changes,
                        )
                    )
                commit_authors_emails = []
                commit_changes = 0

            for commit_line in commit_data.stdout.splitlines():
                if self.__AUTHOR_REG.fullmatch(string=commit_line):
                    finish_commit()
                    commit_authors_emails = [
                        self.__format_author_email_str(
                            author_str=commit_line.split(self.__AUTHOR_LABEL)[
                                -1
                            ].strip()
                        )
                    ]
                    continue

                co_author: Match[str] | None = self.__CO_AUTHOR_REG.search(
                    string=commit_line
                )
                if co_author:
                    commit_authors_emails.append(
                        self.__format_author_email_str(
                            author_str=co_author.group()
                            .lower()
                            .split(self.__CO_AUTHOR_LABEL.lower())[1]
                            .strip()
                        )
                    )
                    continue

                if commit_authors_emails and self.__NUMSTAT_REG.match(
                    string=commit_line
                ):
                    add_str, del_str, _ = commit_line.split(sep="\t")
                    if add_str.isdigit() and del_str.isdigit():
                        commit_changes += int(add_str) + int(del_str)

            finish_commit()

        except CalledProcessError as err:
            raise RepoPinStatsError(
                msg=f"Git process error: {err.stderr.strip() or err.stdout.strip() or err}"
            )
        finally:
            rmtree(path=tmp_dir, ignore_errors=True)

        if not commits:
            return []

        id_idx: dict[tuple[str, str | None], int] = {}
        obs: list[ContributorIdObs] = []

        def id_node(author: str, email: str | None) -> int:
            key: tuple[str, str | None] = (author, email)
            existing_id = id_idx.get(key)
            if existing_id is not None:
                return existing_id

            obs_idx: int = len(obs)
            id_idx[key] = obs_idx
            obs.append(
                ContributorIdObs.create(
                    names={author},
                    emails={email} if email else None,
                )
            )
            return obs_idx

        commit_nodes: list[tuple[list[int], int]] = [
            (
                [
                    id_node(author=author, email=email)
                    for author, email in commit_authors
                ],
                commit_changes,
            )
            for commit_authors, commit_changes in commits
        ]

        resolver: ContributorIdResolver = ContributorIdResolver(obs=obs)
        roots: list[int] = resolver.resolve()

        contributor_authors: dict[int, set[str]] = {}
        contributor_emails: dict[int, set[str]] = {}
        for (author, email), idx in id_idx.items():
            contributor_authors.setdefault(roots[idx], set()).add(author)
            contributor_emails.setdefault(roots[idx], set())
            if email:
                contributor_emails[roots[idx]].add(email)

        contributor_stats: dict[int, float | int] = {
            root: 0.0 for root in contributor_authors
        }
        for nodes, commit_changes in commit_nodes:
            contributor_roots: set[int] = {roots[node] for node in nodes}
            if not contributor_roots:
                continue
            contribution_share: float | int = commit_changes / len(contributor_roots)
            for root in contributor_roots:
                contributor_stats[root] += contribution_share

        return [
            {
                enums.RepoPinsResDictKeys.LOGIN.value: max(
                    contributor_authors[root],
                    key=lambda value: (len(value), value),
                ),
                enums.RepoPinsResDictKeys.STATS.value: contributor_stats[root],
                enums.RepoPinsResDictKeys.AUTHOR.value: contributor_authors[root],
                enums.RepoPinsResDictKeys.EMAIL.value: contributor_emails[root],
            }
            for root in sorted(
                contributor_authors,
                key=lambda root_i: (
                    -contributor_stats[root],
                    max(contributor_authors[root]).casefold(),
                ),
            )
        ]

    def fetch_contribution_stats(
        self,
        repo_list: list[dict[str, Any]],
        include_percentage_stats: bool = True,
        raise_errors: bool = True,
    ) -> list[dict[str, Any]]:
        tasks: list[tuple[str, dict]] = []
        for repo in repo_list:
            url_tokens: list[str] = (
                repo.get(enums.RepoPinsResDictKeys.URL.value, "").strip().split("/")
            )
            repo_name: str = repo.get(enums.RepoPinsResDictKeys.NAME.value, "").strip()
            if len(url_tokens) < 2 or not repo_name:
                continue
            tasks.append((f"{url_tokens[-2].strip()}/{repo_name}", repo))
        with ThreadPoolExecutor(
            max_workers=min(self.__MAX_WORKERS, max(1, len(repo_list)))
        ) as thread_pool:
            contribution_data = {
                thread_pool.submit(self.__fetch_repo_stats, owner_repo): repo
                for owner_repo, repo in tasks
            }
            for k_complete in as_completed(contribution_data):
                repo = contribution_data[k_complete]
                try:
                    local_contributors = k_complete.result()
                except RepoPinStatsError:
                    if raise_errors:
                        raise
                    local_contributors = []
                repo[enums.RepoPinsResDictKeys.LOCAL_CONTRIBUTORS.value] = (
                    local_contributors
                )
                if include_percentage_stats:
                    repo[enums.RepoPinsResDictKeys.CONTRIBUTION.value] = (
                        local_contributors
                    )
        return repo_list
