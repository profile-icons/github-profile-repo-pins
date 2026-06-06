from gh_profile_repo_pins.repo_pins_exceptions import RepoPinStatsError
from subprocess import run, PIPE, CompletedProcess, CalledProcessError
from concurrent.futures import ThreadPoolExecutor, as_completed
import gh_profile_repo_pins.repo_pins_enum as enums
from re import compile, I, Pattern
from tempfile import mkdtemp
from shutil import rmtree
from os import environ


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

    def __init__(self, gh_token: str = None) -> None:
        self.__gh_token: str = gh_token

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

    def __fetch_repo_stats(
        self, owner_repo: str
    ) -> list[dict[str, str | dict[str, int]]]:
        url: str = (
            f"https://{(self.__gh_token + "@") if self.__gh_token else ""}github.com/{owner_repo}.git"
        )
        tmp_dir: str = mkdtemp(prefix=self.__TMP_DIR)

        repo_file_changes_add, repo_file_changes_del, commit_log_author_emails = (
            {},
            {},
            {},
        )
        try:
            commit_data: CompletedProcess[str] | None = self.__fetch_git_commit_data(
                url=url, tmp_dir=tmp_dir
            )
            if not commit_data or not commit_data.stdout:
                return []

            commit_authors_emails: list[tuple[str, str | None]] = []
            for commit_line in commit_data.stdout.splitlines():
                if self.__AUTHOR_REG.fullmatch(string=commit_line):
                    commit_authors_emails = [
                        self.__format_author_email_str(
                            author_str=commit_line.split(self.__AUTHOR_LABEL)[
                                -1
                            ].strip()
                        )
                    ]
                    continue
                co_author = self.__CO_AUTHOR_REG.search(string=commit_line)
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
                        is_email_match: bool = False
                        for commit_author, commit_email in commit_authors_emails:
                            commit_author_key: str = commit_author
                            for (
                                commit_log_author,
                                commit_log_id,
                            ) in commit_log_author_emails.items():
                                for commit_log_email in commit_log_id.get(
                                    enums.RepoPinsResDictKeys.EMAIL.value, set()
                                ):
                                    if commit_log_email == commit_email:
                                        if len(commit_log_author) > len(commit_author):
                                            commit_author_key = commit_log_author
                                        is_email_match = True
                                        break
                                if is_email_match:
                                    break

                            repo_file_changes_add[commit_author_key] = (
                                repo_file_changes_add.get(commit_author_key, 0)
                                + int(add_str) // len(commit_authors_emails)
                            )
                            repo_file_changes_del[commit_author_key] = (
                                repo_file_changes_del.get(commit_author_key, 0)
                                + int(del_str) // len(commit_authors_emails)
                            )

                            commit_log_author_emails[commit_author_key] = (
                                commit_log_author_emails.get(
                                    commit_author_key,
                                    {
                                        enums.RepoPinsResDictKeys.AUTHOR.value: set(),
                                        enums.RepoPinsResDictKeys.EMAIL.value: set(),
                                    },
                                )
                            )
                            commit_log_author_emails[commit_author_key][
                                enums.RepoPinsResDictKeys.AUTHOR.value
                            ].add(commit_author)
                            commit_log_author_emails[commit_author_key][
                                enums.RepoPinsResDictKeys.EMAIL.value
                            ].add(commit_email)

        except CalledProcessError as err:
            raise RepoPinStatsError(
                msg=f"Git process error: {err.stderr.strip() or err.stdout.strip() or err}"
            )
        finally:
            rmtree(path=tmp_dir, ignore_errors=True)

        commit_authors: set[str] = set(repo_file_changes_add.keys())
        return [
            {
                enums.RepoPinsResDictKeys.LOGIN.value: commit_author,
                enums.RepoPinsResDictKeys.STATS.value: (
                    repo_file_changes_add.get(commit_author, 0)
                    + repo_file_changes_del.get(commit_author, 0)
                ),
                enums.RepoPinsResDictKeys.AUTHOR.value: (
                    commit_log_author_emails[commit_author][
                        enums.RepoPinsResDictKeys.AUTHOR.value
                    ]
                ),
                enums.RepoPinsResDictKeys.EMAIL.value: (
                    commit_log_author_emails[commit_author][
                        enums.RepoPinsResDictKeys.EMAIL.value
                    ]
                ),
            }
            for commit_author in commit_authors
        ]

    def fetch_contribution_stats(self, repo_list: list[dict]) -> list[dict]:
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
                contribution_data[k_complete][
                    enums.RepoPinsResDictKeys.CONTRIBUTION.value
                ] = k_complete.result()
        return repo_list
