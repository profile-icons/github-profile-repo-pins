from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_policy import (
    RepoPinStatsPolicy,
)
from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_config import (
    RepoPinStatsConfig,
)
from subprocess import PIPE, CompletedProcess, run
from os import environ
from re import Match


class RepoPinStatsGit:

    @staticmethod
    def get_complete_proc(
        args: list[str], input_text: str | None = None
    ) -> CompletedProcess[str]:
        env: dict[str, str] = environ.copy()
        for key, value in (
            ("GIT_TERMINAL_PROMPT", "0"),
            ("GIT_OPTIONAL_LOCKS", "0"),
            ("GIT_ASKPASS", "true"),
            ("GIT_PAGER", "cat"),
            ("GIT_LFS_SKIP_SMUDGE", "1"),
            ("GIT_HTTP_LOW_SPEED_LIMIT", "1024"),
            ("GIT_HTTP_LOW_SPEED_TIME", "60"),
        ):
            env.setdefault(key, value)

        return run(
            args=args,
            check=RepoPinStatsConfig.IS_PROC_ERR,
            stdout=PIPE,
            stderr=PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            input=input_text,
            env=env,
            timeout=RepoPinStatsConfig.GIT_PROC_TO_S,
        )

    @classmethod
    def raw_blob_ids(cls, output: str) -> list[str]:
        zeros: str = "0" * 40
        blob_ids: set[str] = set()
        for line in output.splitlines():
            match: Match[str] | None = RepoPinStatsConfig.RAW_DIFF_REG.fullmatch(
                string=line
            )
            if match is None:
                continue
            for blob in (match.group(1), match.group(2)):
                if blob and blob != zeros and set[str](blob) != {"0"}:
                    blob_ids.add(blob)
        return sorted(blob_ids)

    def prefetch_blobs(self, repo_dir: str, blob_ids: list[str]) -> None:
        for start in range(
            0, len(blob_ids), RepoPinStatsConfig.BLOB_PREFETCH_BATCH_SIZE
        ):
            batch: list[str] = blob_ids[
                start : start + RepoPinStatsConfig.BLOB_PREFETCH_BATCH_SIZE
            ]
            if not batch:
                continue

            safe_batch: list[str] = [
                blob.lower()
                for blob in batch
                if len(blob) == 40
                and all(ch in "0123456789abcdefABCDEF" for ch in blob)
            ]
            if not safe_batch:
                continue
            self.get_complete_proc(
                args=[
                    "git",
                    "-C",
                    repo_dir,
                    "-c",
                    "fetch.negotiationAlgorithm=noop",
                    "fetch",
                    "origin",
                    "--no-tags",
                    "--no-write-fetch-head",
                    "--recurse-submodules=no",
                    "--filter=blob:none",
                    *safe_batch,
                ]
            )

    def fetch_commit_data(
        self, url: str, tmp_dir: str
    ) -> tuple[CompletedProcess[str], CompletedProcess[str], CompletedProcess[str]]:
        self.get_complete_proc(
            args=[
                "git",
                "clone",
                "--no-tags",
                "--single-branch",
                "--no-checkout",
                "--filter=blob:none",
                url,
                tmp_dir,
            ]
        )

        log_args: list[str] = [
            "git",
            "-C",
            tmp_dir,
            "-c",
            "i18n.logOutputEncoding=UTF-8",
            "-c",
            "core.quotePath=false",
            "log",
            "HEAD",
            "--use-mailmap",
            "--reverse",
            "--topo-order",
        ]
        commit_format: str = "{} %H %T %P%n{} %aN <%aE>%n{} %an <%ae>%n%B%n".format(
            RepoPinStatsConfig.COMMIT_LBL,
            RepoPinStatsConfig.AUTH_LBL,
            RepoPinStatsConfig.RAW_AUTH_LBL,
        )

        metadata: CompletedProcess[str] = self.get_complete_proc(
            args=[*log_args, "--no-patch", f"--format={commit_format}"]
        )

        raw_changes: CompletedProcess[str] = self.get_complete_proc(
            args=[
                *log_args,
                "--full-history",
                "--no-diff-merges",
                "--raw",
                "--no-renames",
                "--abbrev=40",
                "--format=",
                "--",
                *RepoPinStatsPolicy.cred_hist_path_specs(),
            ]
        )
        self.prefetch_blobs(
            repo_dir=tmp_dir,
            blob_ids=self.raw_blob_ids(output=raw_changes.stdout),
        )

        return (
            metadata,
            self.get_complete_proc(
                args=[
                    *log_args,
                    "--full-history",
                    "--no-diff-merges",
                    "--raw",
                    "--patch",
                    "--unified=0",
                    "--find-renames=20%",
                    "--abbrev=40",
                    f"--format={commit_format}",
                    "--",
                    *RepoPinStatsPolicy.cred_hist_path_specs(is_exclude_nb=True),
                ]
            ),
            self.get_complete_proc(
                args=[
                    *log_args,
                    "--full-history",
                    "--no-diff-merges",
                    "--raw",
                    "--no-renames",
                    "--abbrev=40",
                    f"--format={commit_format}",
                    "--",
                    ":(icase,glob)**/*.ipynb",
                ]
            ),
        )
