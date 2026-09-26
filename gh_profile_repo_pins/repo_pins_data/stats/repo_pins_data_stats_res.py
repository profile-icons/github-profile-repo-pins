from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_models import (
    AuthorId,
    Commit,
    CreditCommit,
)
from gh_profile_repo_pins.repo_pins_data.repo_pins_data_contributor_id import (
    ContributorIdObs,
    ContributorIdResolver,
)
import gh_profile_repo_pins.repo_pins_enum as enums
from typing import Any


class RepoPinStatsResults:

    @staticmethod
    def resolve_contributors(
        cred_commits: list[CreditCommit],
    ) -> tuple[
        dict[int, set[str]],
        dict[int, set[str]],
        dict[int, float | int],
        dict[int, int],
    ]:
        cred_commits = [item for item in cred_commits if item[1] > 0 and item[2] > 0]
        if not cred_commits:
            return {}, {}, {}, {}

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
            for authors, changes, credit in cred_commits
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

    @staticmethod
    def build_contributors(
        commits: list[Commit], cred_commits: list[CreditCommit]
    ) -> list[dict[str, Any]]:
        (
            contributor_authors,
            contributor_emails,
            contributor_stats,
            contributor_commits,
        ) = RepoPinStatsResults.resolve_contributors(cred_commits=cred_commits)

        res: list[dict[str, Any]] = [
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

        RepoPinStatsResults.attach_profile_commits(
            contributors=res, commits=commits, cred_commits=cred_commits
        )
        return res

    @staticmethod
    def attach_profile_commits(
        contributors: list[dict[str, Any]],
        commits: list[Commit],
        cred_commits: list[CreditCommit],
    ) -> None:
        max_profile_commits: int = 3

        def attach_commit(_id: AuthorId, sha: str) -> None:
            id_names, id_emails = _id
            for contributor in contributors:
                names: set[str] = set(
                    contributor.get(enums.RepoPinsResDictKeys.AUTHOR.value, set())
                    or set()
                )
                emails: set[str] = set(
                    contributor.get(enums.RepoPinsResDictKeys.EMAIL.value, set())
                    or set()
                )
                if not ((set[str](id_names) & names) or (set[str](id_emails) & emails)):
                    continue
                commit_shas = list(
                    contributor.get(enums.RepoPinsResDictKeys.PROFILE_COMMITS.value, [])
                    or []
                )
                if sha not in commit_shas and len(commit_shas) < max_profile_commits:
                    commit_shas.append(sha)
                    contributor[enums.RepoPinsResDictKeys.PROFILE_COMMITS.value] = (
                        commit_shas
                    )
                    contributor[enums.RepoPinsResDictKeys.PROFILE_COMMIT.value] = (
                        commit_shas[0]
                    )
                return

        co_commits: list[tuple[Commit, CreditCommit]] = list(zip(commits, cred_commits))
        for commit, (authors, changes, credit) in reversed(co_commits):
            if changes <= 0 or credit <= 0 or not authors:
                continue
            attach_commit(_id=authors[0], sha=commit.hash)

        for commit, (authors, changes, credit) in reversed(co_commits):
            if changes <= 0 or credit <= 0:
                continue
            for _id in authors:
                attach_commit(_id=_id, sha=commit.hash)
