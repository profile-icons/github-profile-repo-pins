from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_models import (
    AuthorId,
    Commit,
    CreditCommit,
    LineChangeKey,
)
from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_attr import (
    RepoPinStatsAttribution,
)
from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_parser import (
    RepoPinStatsParser,
)
from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_policy import (
    RepoPinStatsPolicy,
)
from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_config import (
    RepoPinStatsConfig,
)
from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_res import (
    RepoPinStatsResults,
)
from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_git import (
    RepoPinStatsGit,
)
from subprocess import CalledProcessError, CompletedProcess, TimeoutExpired
from gh_profile_repo_pins.repo_pins_exceptions import RepoPinStatsError
from concurrent.futures import ThreadPoolExecutor, as_completed
import gh_profile_repo_pins.repo_pins_enum as enums
from collections import Counter
from tempfile import mkdtemp
from shutil import rmtree
from typing import Any
from re import Match


class RepoPinStats:

    __TMP_DIR: str = RepoPinStatsConfig.TMP_DIR
    __MAX_WORKERS: int = RepoPinStatsConfig.MAX_WORKERS
    __GIT_PROC_TO_S: int = RepoPinStatsConfig.GIT_PROC_TO_S

    def __init__(self, gh_token: str | None = None) -> None:
        self.__gh_token: str | None = gh_token
        self.__git: RepoPinStatsGit = RepoPinStatsGit()
        self.__parser: RepoPinStatsParser = RepoPinStatsParser(git=self.__git)

    def __get_complete_proc(
        self, args: list[str], input_text: str | None = None
    ) -> CompletedProcess[str]:
        return self.__git.get_complete_proc(args=args, input_text=input_text)

    @classmethod
    def __cred_hist_path_specs(cls, is_exclude_nb: bool = False) -> list[str]:
        return RepoPinStatsPolicy.cred_hist_path_specs(is_exclude_nb=is_exclude_nb)

    @classmethod
    def __raw_blob_ids(cls, output: str) -> list[str]:
        return RepoPinStatsGit.raw_blob_ids(output=output)

    def __prefetch_blobs(self, repo_dir: str, blob_ids: list[str]) -> None:
        self.__git.prefetch_blobs(repo_dir=repo_dir, blob_ids=blob_ids)

    def __fetch_commit_data(
        self, url: str, tmp_dir: str
    ) -> tuple[CompletedProcess[str], CompletedProcess[str], CompletedProcess[str]]:
        return self.__git.fetch_commit_data(url=url, tmp_dir=tmp_dir)

    @staticmethod
    def __merge_patch_data(commits: list[Commit], patch_commits: list[Commit]) -> None:
        RepoPinStatsParser.merge_patch_data(
            commits=commits, patch_commits=patch_commits
        )

    @staticmethod
    def __id_from_match(match: Match[str]) -> AuthorId:
        return RepoPinStatsParser.id_from_match(match=match)

    @staticmethod
    def __append_commit(commits: list[Commit], commit: Commit | None) -> None:
        RepoPinStatsParser.append_commit(commits=commits, commit=commit)

    @classmethod
    def __is_cred_path(cls, path: str) -> bool:
        return RepoPinStatsPolicy.is_cred_path(path=path)

    @staticmethod
    def __is_nb_path(path: str | None) -> bool:
        return RepoPinStatsPolicy.is_nb_path(path=path)

    @classmethod
    def __is_cred_patch_path(cls, path: str) -> bool:
        return RepoPinStatsPolicy.is_cred_patch_path(path=path)

    def __parse_commits(self, output: str, repo_dir: str | None = None) -> list[Commit]:
        return self.__parser.parse_commits(output=output, repo_dir=repo_dir)

    @staticmethod
    def __nb_src_lines(raw: str) -> list[str]:
        return RepoPinStatsParser.nb_src_lines(raw=raw)

    def __populate_nb_changes(self, commits: list[Commit], repo_dir: str) -> None:
        self.__parser.populate_nb_changes(commits=commits, repo_dir=repo_dir)

    @staticmethod
    def __is_ancestor(
        ancs_idx: int,
        desc_idx: int,
        commits: list[Commit],
        commit_idx_by_hash: dict[str, int],
        cache: dict[tuple[int, int], bool],
    ) -> bool:
        return RepoPinStatsAttribution.is_ancestor(
            ancs_idx=ancs_idx,
            desc_idx=desc_idx,
            commits=commits,
            commit_idx_by_hash=commit_idx_by_hash,
            cache=cache,
        )

    @staticmethod
    def __path_rename_frag(old_path: str, new_path: str) -> tuple[str, str] | None:
        return RepoPinStatsAttribution.path_rename_frag(
            old_path=old_path, new_path=new_path
        )

    @classmethod
    def __rename_replacements(cls, commit: Commit) -> list[tuple[str, str]]:
        return RepoPinStatsAttribution.rename_replacements(commit=commit)

    @classmethod
    def __exclude_mech_refactors(
        cls, commit: Commit
    ) -> tuple[Counter[LineChangeKey], Counter[LineChangeKey]]:
        return RepoPinStatsAttribution.exclude_mech_refactors(commit=commit)

    @classmethod
    def __code_line(cls, line: str) -> str:
        return RepoPinStatsAttribution.code_line(line=line)

    @classmethod
    def __exclude_code_base_rewrite(
        cls,
        commit: Commit,
        dels: Counter[LineChangeKey],
        adds: Counter[LineChangeKey],
    ) -> tuple[Counter[LineChangeKey], Counter[LineChangeKey]]:
        return RepoPinStatsAttribution.exclude_code_base_rewrite(
            commit=commit, dels=dels, adds=adds
        )

    @staticmethod
    def __patch_sig(commit: Commit) -> str | None:
        return RepoPinStatsAttribution.patch_sig(commit=commit)

    @classmethod
    def __valid_change_sum(cls, commits: list[Commit]) -> list[tuple[int, int]]:
        return RepoPinStatsAttribution.valid_change_sum(commits=commits)

    @classmethod
    def __is_auto_id(cls, auth_id: AuthorId) -> bool:
        return RepoPinStatsPolicy.is_auto_id(auth_id=auth_id)

    @classmethod
    def __cred_commits(cls, commits: list[Commit]) -> list[CreditCommit]:
        return RepoPinStatsAttribution.cred_commits(commits=commits)

    @staticmethod
    def __resolve_contributors(
        cred_commits: list[CreditCommit],
    ) -> tuple[
        dict[int, set[str]],
        dict[int, set[str]],
        dict[int, float | int],
        dict[int, int],
    ]:
        return RepoPinStatsResults.resolve_contributors(cred_commits=cred_commits)

    def __fetch_repo_stats(self, owner_repo: str) -> list[dict[str, Any]]:
        tmp_dir: str = mkdtemp(prefix=self.__TMP_DIR)

        try:
            metadata, patches, nbs = self.__fetch_commit_data(
                url=f"https://{f'{self.__gh_token}@' if self.__gh_token else ''}github.com/{owner_repo}.git",
                tmp_dir=tmp_dir,
            )
            if not metadata.stdout:
                return []
            commits: list[Commit] = self.__parse_commits(output=metadata.stdout)
            patch_commits: list[Commit] = self.__parse_commits(output=patches.stdout)
            nb_commits: list[Commit] = self.__parse_commits(
                output=nbs.stdout, repo_dir=tmp_dir
            )
            self.__merge_patch_data(commits=commits, patch_commits=patch_commits)
            self.__merge_patch_data(commits=commits, patch_commits=nb_commits)
        except CalledProcessError as err:
            raise RepoPinStatsError(
                msg=f"Git process error: {err.stderr.strip() or err.stdout.strip() or err}"
            )
        except TimeoutExpired as _:
            raise RepoPinStatsError(
                msg=f"Git process timed out after {self.__GIT_PROC_TO_S} seconds."
            )
        finally:
            rmtree(path=tmp_dir, ignore_errors=True)

        if not commits:
            return []

        cred_commits: list[tuple[list[tuple[set[str], set[str]]], int, int]] = (
            self.__cred_commits(commits=commits)
        )
        return RepoPinStatsResults.build_contributors(
            commits=commits, cred_commits=cred_commits
        )

    def fetch_contribution_stats(
        self,
        repo_list: list[dict[str, Any]],
        is_contribution_stats: bool = True,
        is_raise_err: bool = True,
    ) -> list[dict[str, str]]:
        tasks: list[tuple[str, dict[str, Any]]] = []
        for repo in repo_list:
            url_tokens: str = (
                repo.get(enums.RepoPinsResDictKeys.URL.value, "").strip().split("/")
            )
            repo_name: str = repo.get(enums.RepoPinsResDictKeys.NAME.value, "").strip()
            if len(url_tokens) >= 2 and repo_name:
                tasks.append((f"{url_tokens[-2].strip()}/{repo_name}", repo))

        if not tasks:
            return repo_list

        if is_contribution_stats:
            for owner_repo, repo in tasks:
                try:
                    contributors: list[dict[str, Any]] = self.__fetch_repo_stats(
                        owner_repo=owner_repo
                    )
                except RepoPinStatsError:
                    if is_raise_err:
                        raise
                    contributors = []

                repo[enums.RepoPinsResDictKeys.LOCAL_CONTRIBUTORS.value] = contributors
                repo[enums.RepoPinsResDictKeys.CONTRIBUTION.value] = contributors
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
                    contributors = completed.result()
                except RepoPinStatsError:
                    if is_raise_err:
                        raise
                    contributors = []

                repo[enums.RepoPinsResDictKeys.LOCAL_CONTRIBUTORS.value] = contributors

        return repo_list
