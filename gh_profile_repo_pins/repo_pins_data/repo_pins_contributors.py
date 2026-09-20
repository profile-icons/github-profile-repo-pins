from gh_profile_repo_pins.repo_pins_data.repo_pins_contributor_id import (
    ContributorIdObs,
    ContributorIdResolver,
    norm_val,
    norm_vals,
)
import gh_profile_repo_pins.repo_pins_enum as enums
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResolvedContributor:
    login: str
    names: frozenset[str]
    emails: frozenset[str]
    user_id: int | None
    avatar_url: str | None
    stats: float | int
    commit_count: int
    is_user: bool = False


@dataclass(frozen=True)
class ContributorResolution:
    contributors: tuple[ResolvedContributor, ...]
    contribution_perc: float | int
    user_idx: int | None

    @property
    def count(self) -> int:
        return len(self.contributors)


def _local_id(data: dict[str, Any]) -> tuple[str, set[str], set[str]]:
    authors: set[str] = norm_vals(
        vals=data.get(enums.RepoPinsResDictKeys.AUTHOR.value, [])
    )
    login: str = norm_val(val=data.get(enums.RepoPinsResDictKeys.LOGIN.value, ""))
    if login:
        authors.add(login)
    return (
        login,
        authors,
        norm_vals(vals=data.get(enums.RepoPinsResDictKeys.EMAIL.value, [])),
    )


def _github_id(
    data: dict[str, Any],
) -> tuple[str, set[str], set[str], int | None]:
    authors = norm_vals(vals=data.get(enums.RepoPinsResDictKeys.AUTHOR.value, []))
    authors.update(norm_vals(vals=data.get(enums.RepoPinsResDictKeys.NAME.value)))

    login: str = norm_val(val=data.get(enums.RepoPinsResDictKeys.LOGIN.value, ""))
    if login:
        authors.add(login)

    raw_id: int | float | None = data.get("id")
    user_id: int | None = int(raw_id) if raw_id is not None else None
    emails: set[str] = norm_vals(
        vals=data.get(enums.RepoPinsResDictKeys.EMAIL.value, [])
    )
    if login:
        emails.add(f"{login}@users.noreply.github.com")
        if user_id is not None:
            emails.add(f"{user_id}+{login}@users.noreply.github.com")
    return login, authors, emails, user_id


def _is_local_user(
    data: dict[str, Any],
    login_username: str,
    login_user_name: str,
    login_user_id: int | None,
) -> bool:
    _, authors, emails = _local_id(data=data)
    login_username_norm: str = norm_val(val=login_username)
    login_user_name_norm: str = norm_val(val=login_user_name)
    account_no_reply_email: str = (
        f"{login_user_id}+{login_username_norm}@users.noreply.github.com"
        if login_user_id is not None and login_username_norm
        else ""
    )
    return (
        (bool(login_user_name_norm) and login_user_name_norm in authors)
        or (bool(login_username_norm) and login_username_norm in authors)
        or (bool(account_no_reply_email) and account_no_reply_email in emails)
        or (
            login_user_id is not None
            and any(
                email.startswith(f"{login_user_id}+")
                and email.endswith("@users.noreply.github.com")
                for email in emails
            )
        )
    )


def collapse_local_contributors(
    contributors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(contributors) <= 1:
        return contributors

    groups = ContributorIdResolver(
        obs=[
            ContributorIdObs.create(
                names=_local_id(data=data)[1],
                emails=_local_id(data=data)[2],
            )
            for data in contributors
        ]
    ).groups()

    merged_contributors: list[dict[str, Any]] = []
    for idxes in groups.values():
        merged: dict[str, Any] = {
            enums.RepoPinsResDictKeys.LOGIN.value: "",
            enums.RepoPinsResDictKeys.STATS.value: 0.0,
            enums.RepoPinsResDictKeys.AUTHOR.value: set(),
            enums.RepoPinsResDictKeys.EMAIL.value: set(),
        }
        for idx in idxes:
            contributor: dict[str, Any] = contributors[idx]
            local_login, local_authors, local_emails = _local_id(data=contributor)
            merged[enums.RepoPinsResDictKeys.STATS.value] = float(
                merged.get(enums.RepoPinsResDictKeys.STATS.value, 0.0)
            ) + float(contributor.get(enums.RepoPinsResDictKeys.STATS.value, 0) or 0)
            merged[enums.RepoPinsResDictKeys.AUTHOR.value].update(local_authors)
            merged[enums.RepoPinsResDictKeys.EMAIL.value].update(local_emails)
            if len(local_login) > len(
                str(merged.get(enums.RepoPinsResDictKeys.LOGIN.value, "") or "")
            ):
                merged[enums.RepoPinsResDictKeys.LOGIN.value] = local_login

        if not merged[enums.RepoPinsResDictKeys.LOGIN.value]:
            authors = merged[enums.RepoPinsResDictKeys.AUTHOR.value]
            if authors:
                merged[enums.RepoPinsResDictKeys.LOGIN.value] = max(
                    authors, key=lambda value: (len(value), value)
                )
        merged_contributors.append(merged)
    return merged_contributors


def dedupe_github_contributors(
    contributors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(contributors) <= 1:
        return contributors

    ids: list[tuple[str, set[str], set[str], int | None]] = [
        _github_id(data=data) for data in contributors
    ]
    groups: dict[int, list[int]] = ContributorIdResolver(
        obs=[
            ContributorIdObs.create(
                names=authors,
                emails=emails,
                login=login,
                user_id=user_id,
            )
            for login, authors, emails, user_id in ids
        ]
    ).groups()

    deduped: list[dict[str, Any]] = []
    for idxes in groups.values():
        merged: dict[str, Any] = {
            enums.RepoPinsResDictKeys.LOGIN.value: "",
            enums.RepoPinsResDictKeys.AUTHOR.value: set(),
            enums.RepoPinsResDictKeys.EMAIL.value: set(),
            enums.RepoPinsResDictKeys.CONTRIBUTIONS.value: 0,
        }
        for idx in idxes:
            data: dict[str, Any] = contributors[idx]
            login, authors, emails, user_id = ids[idx]
            merged[enums.RepoPinsResDictKeys.AUTHOR.value].update(authors)
            merged[enums.RepoPinsResDictKeys.EMAIL.value].update(emails)
            if login and not merged[enums.RepoPinsResDictKeys.LOGIN.value]:
                merged[enums.RepoPinsResDictKeys.LOGIN.value] = str(
                    data.get(enums.RepoPinsResDictKeys.LOGIN.value, "") or ""
                ).strip()
            if user_id is not None and merged.get("id") is None:
                merged["id"] = user_id
            if not merged.get(enums.RepoPinsResDictKeys.AVATAR_URL.value) and data.get(
                enums.RepoPinsResDictKeys.AVATAR_URL.value
            ):
                merged[enums.RepoPinsResDictKeys.AVATAR_URL.value] = data.get(
                    enums.RepoPinsResDictKeys.AVATAR_URL.value
                )
            merged[enums.RepoPinsResDictKeys.CONTRIBUTIONS.value] = max(
                int(merged.get(enums.RepoPinsResDictKeys.CONTRIBUTIONS.value, 0) or 0),
                int(data.get(enums.RepoPinsResDictKeys.CONTRIBUTIONS.value, 0) or 0),
            )
        deduped.append(merged)
    return deduped


def _is_profile_linked(data: dict[str, Any]) -> bool:
    login, _, _, user_id = _github_id(data=data)
    return bool(
        user_id is not None
        or login
        or data.get(enums.RepoPinsResDictKeys.AVATAR_URL.value)
    )


def resolve_repo_contributors(
    repo_data: dict[str, Any],
    login_username: str,
    login_user_name: str,
    login_user_id: int | None,
) -> ContributorResolution:
    contribution_data: list[dict[str, Any]] = (
        repo_data.get(enums.RepoPinsResDictKeys.CONTRIBUTION.value, []) or []
    )
    local_contributors: list[dict[str, Any]] = (
        repo_data.get(enums.RepoPinsResDictKeys.LOCAL_CONTRIBUTORS.value, []) or []
    )
    if not local_contributors:
        local_contributors = [
            data
            for data in contribution_data
            if enums.RepoPinsResDictKeys.STATS.value in data
        ]

    github_contributors: list[dict[str, Any]] = (
        repo_data.get(enums.RepoPinsResDictKeys.CONTRIBUTORS.value, []) or []
    )
    if not github_contributors:
        github_contributors = [
            data
            for data in contribution_data
            if data.get(enums.RepoPinsResDictKeys.AVATAR_URL.value)
        ]

    local_contributors = collapse_local_contributors(contributors=local_contributors)
    github_contributors = dedupe_github_contributors(contributors=github_contributors)

    obs: list[ContributorIdObs] = []
    srcs: list[tuple[str, int]] = []

    for idx, data in enumerate[dict[str, Any]](local_contributors):
        local_login, local_authors, local_emails = _local_id(data=data)
        is_user: bool = _is_local_user(
            data=data,
            login_username=login_username,
            login_user_name=login_user_name,
            login_user_id=login_user_id,
        )
        obs.append(
            ContributorIdObs.create(
                names=local_authors | ({local_login} if local_login else set()),
                emails=local_emails,
                login=(login_username if is_user else ""),
                user_id=(login_user_id if is_user else None),
            )
        )
        srcs.append(("local", idx))

    for idx, data in enumerate[dict[str, Any]](github_contributors):
        login, authors, emails, user_id = _github_id(data=data)
        obs.append(
            ContributorIdObs.create(
                names=authors,
                emails=emails,
                login=login,
                user_id=user_id,
            )
        )
        srcs.append(("github", idx))

    if not obs:
        return ContributorResolution(
            contributors=(), contribution_perc=0, user_idx=None
        )

    groups: dict[int, list[int]] = ContributorIdResolver(obs=obs).groups()
    login_username_norm: str = norm_val(val=login_username)
    resolved: list[ResolvedContributor] = []

    for idxes in groups.values():
        local_idxes: list[int] = [
            srcs[idx][1] for idx in idxes if srcs[idx][0] == "local"
        ]
        github_idxes: list[int] = [
            srcs[idx][1] for idx in idxes if srcs[idx][0] == "github"
        ]

        if local_contributors and not local_idxes:
            is_linked: bool = any(
                _is_profile_linked(data=github_contributors[idx])
                for idx in github_idxes
            )
            if not is_linked:
                continue

        names: set[str] = set()
        emails = set()
        local_logins: list[str] = []
        stats: float | int = 0.0
        is_user = False
        for idx in local_idxes:
            data = local_contributors[idx]
            local_login, local_authors, local_emails = _local_id(data=data)
            names.update(local_authors)
            emails.update(local_emails)
            if local_login:
                local_logins.append(local_login)
            stats += float(data.get(enums.RepoPinsResDictKeys.STATS.value, 0) or 0)
            if _is_local_user(
                data=data,
                login_username=login_username,
                login_user_name=login_user_name,
                login_user_id=login_user_id,
            ):
                is_user = True

        github_login: str = ""
        avatar_url: str | None = None
        user_id = None
        commit_count: int = 0
        for idx in github_idxes:
            data = github_contributors[idx]
            login, github_authors, github_emails, github_user_id = _github_id(data=data)
            names.update(github_authors)
            emails.update(github_emails)
            if login and not github_login:
                github_login = str(
                    data.get(enums.RepoPinsResDictKeys.LOGIN.value, "") or ""
                ).strip()
            if github_user_id is not None and user_id is None:
                user_id = github_user_id
            if not avatar_url and data.get(enums.RepoPinsResDictKeys.AVATAR_URL.value):
                avatar_url = str(data[enums.RepoPinsResDictKeys.AVATAR_URL.value])
            commit_count = max(
                commit_count,
                int(data.get(enums.RepoPinsResDictKeys.CONTRIBUTIONS.value, 0) or 0),
            )
            if login_username_norm and login == login_username_norm:
                is_user = True

        login = github_login
        if not login and local_logins:
            login = max(local_logins, key=lambda value: (len(value), value))
        if not login and names:
            login = max(names, key=lambda value: (len(value), value))
        if not login:
            login = "unknown"

        resolved.append(
            ResolvedContributor(
                login=login,
                names=frozenset[str](names),
                emails=frozenset[str](emails),
                user_id=user_id,
                avatar_url=avatar_url,
                stats=stats,
                commit_count=commit_count,
                is_user=is_user,
            )
        )

    has_local_stats: bool = bool(local_contributors)
    resolved.sort(
        key=lambda contributor: (
            contributor.stats if has_local_stats else float(contributor.commit_count),
            contributor.commit_count,
            contributor.login.casefold(),
        ),
        reverse=True,
    )

    user_idx: int | None = next(
        (
            idx
            for idx, contributor in enumerate[ResolvedContributor](resolved)
            if contributor.is_user
        ),
        None,
    )
    contribution_perc: float | int = 0
    is_perc_available: bool = any(
        enums.RepoPinsResDictKeys.STATS.value in data for data in contribution_data
    )
    if is_perc_available:
        total_stats: float | int = sum(contributor.stats for contributor in resolved)
        if total_stats and user_idx is not None:
            contribution_perc = resolved[user_idx].stats / total_stats * 100

    return ContributorResolution(
        contributors=tuple[ResolvedContributor](resolved),
        contribution_perc=contribution_perc,
        user_idx=user_idx,
    )
