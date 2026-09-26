from gh_profile_repo_pins.repo_pins_data.repo_pins_data_contributor_id import (
    ContributorIdObs,
    ContributorIdResolver,
    norm_val,
    norm_vals,
)
import gh_profile_repo_pins.repo_pins_enum as enums
from re import fullmatch, match, Match
from dataclasses import dataclass
from typing import Any

ContributorData = dict[str, Any]
GitHubId = tuple[str, set[str], set[str], int | None]
LocalId = tuple[str, set[str], set[str]]


@dataclass(frozen=True)
class ResContributor:
    login: str
    names: frozenset[str]
    emails: frozenset[str]
    user_id: int | None
    avatar_url: str | None
    stats: float | int
    commit_count: int
    is_user: bool = False


@dataclass(frozen=True)
class ContributorRes:
    contributors: tuple[ResContributor, ...]
    contribution_perc: float | int
    user_idx: int | None

    @property
    def count(self) -> int:
        return len(self.contributors)


def _count(data: ContributorData) -> int:
    return int(data.get(enums.RepoPinsResDictKeys.CONTRIBUTIONS.value, 0) or 0)


def _gh_login_candidate(val: str) -> str:
    val = str(val or "").strip()
    if not val or len(val) > 39:
        return ""
    if not fullmatch(
        pattern=r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", string=val
    ):
        return ""
    return val


def _local_profile_hint(
    login: str,
    authors: set[str],
    emails: set[str],
) -> tuple[str, int | None, str | None]:
    for email in sorted(emails):
        no_reply: Match[str] | None = match(
            pattern=r"^(?:(\d+)\+)?([A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)@users\.noreply\.github\.com$",
            string=email,
            flags=0,
        )
        if not no_reply:
            continue
        user_id, user_login = no_reply.groups()
        if user_id:
            user_id = int(user_id)
            return (
                user_login,
                user_id,
                f"https://avatars.githubusercontent.com/u/{user_id}?v=4",
            )
        return (
            user_login,
            None,
            f"https://github.com/{user_login}.png?size=80",
        )

    candidates: tuple[str, *tuple[str, ...]] = (
        login,
        *sorted(
            authors,
            key=lambda val: (len(val), val),
            reverse=True,
        ),
    )
    for candidate in candidates:
        if user_login := _gh_login_candidate(val=candidate):
            return (
                user_login,
                None,
                f"https://github.com/{user_login}.png?size=80",
            )
    return "", None, None


def _local_id(data: ContributorData) -> LocalId:
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


def _github_id(data: ContributorData) -> GitHubId:
    authors: set[str] = norm_vals(
        vals=data.get(enums.RepoPinsResDictKeys.AUTHOR.value, [])
    )
    authors.update(norm_vals(vals=data.get(enums.RepoPinsResDictKeys.NAME.value)))
    login: str = norm_val(val=data.get(enums.RepoPinsResDictKeys.LOGIN.value, ""))
    if login:
        authors.add(login)

    raw_id: str | None = data.get("id")
    user_id: int | None = int(raw_id) if raw_id is not None else None
    emails: set[str] = norm_vals(
        vals=data.get(enums.RepoPinsResDictKeys.EMAIL.value, [])
    )
    if login:
        emails.add(f"{login}@users.noreply.github.com")
        if user_id is not None:
            emails.add(f"{user_id}+{login}@users.noreply.github.com")
    return login, authors, emails, user_id


def _matches_local_user(
    authors: set[str],
    emails: set[str],
    login_username: str,
    login_user_name: str,
    login_user_id: int | None,
) -> bool:
    username: str = norm_val(val=login_username)
    user_name: str = norm_val(val=login_user_name)
    no_reply: str = (
        f"{login_user_id}+{username}@users.noreply.github.com"
        if login_user_id is not None and username
        else ""
    )
    return (
        (bool(user_name) and user_name in authors)
        or (bool(username) and username in authors)
        or (bool(no_reply) and no_reply in emails)
        or (
            login_user_id is not None
            and any(
                email.startswith(f"{login_user_id}+")
                and email.endswith("@users.noreply.github.com")
                for email in emails
            )
        )
    )


def _is_local_user(
    data: ContributorData,
    login_username: str,
    login_user_name: str,
    login_user_id: int | None,
) -> bool:
    _, authors, emails = _local_id(data=data)
    return _matches_local_user(
        authors=authors,
        emails=emails,
        login_username=login_username,
        login_user_name=login_user_name,
        login_user_id=login_user_id,
    )


def collapse_local_contributors(
    contributors: list[ContributorData],
) -> list[ContributorData]:
    if len(contributors) <= 1:
        return contributors

    ids: list[tuple[str, set[str], set[str]]] = [
        _local_id(data) for data in contributors
    ]
    groups: dict[int, list[int]] = ContributorIdResolver(
        obs=[
            ContributorIdObs.create(names=authors, emails=emails)
            for _, authors, emails in ids
        ]
    ).groups()

    result: list[ContributorData] = []
    for idxes in groups.values():
        merged: ContributorData = {
            enums.RepoPinsResDictKeys.LOGIN.value: "",
            enums.RepoPinsResDictKeys.STATS.value: 0.0,
            enums.RepoPinsResDictKeys.CONTRIBUTIONS.value: 0,
            enums.RepoPinsResDictKeys.AUTHOR.value: set(),
            enums.RepoPinsResDictKeys.EMAIL.value: set(),
        }
        for idx in idxes:
            data: dict[str, Any] = contributors[idx]
            login, authors, emails = ids[idx]
            merged[enums.RepoPinsResDictKeys.STATS.value] += float(
                data.get(enums.RepoPinsResDictKeys.STATS.value, 0) or 0
            )
            merged[enums.RepoPinsResDictKeys.CONTRIBUTIONS.value] += _count(data)
            merged[enums.RepoPinsResDictKeys.AUTHOR.value].update(authors)
            merged[enums.RepoPinsResDictKeys.EMAIL.value].update(emails)
            if len(login) > len(merged[enums.RepoPinsResDictKeys.LOGIN.value]):
                merged[enums.RepoPinsResDictKeys.LOGIN.value] = login

        if not merged[enums.RepoPinsResDictKeys.LOGIN.value]:
            authors = merged[enums.RepoPinsResDictKeys.AUTHOR.value]
            if authors:
                merged[enums.RepoPinsResDictKeys.LOGIN.value] = max(
                    authors, key=lambda value: (len(value), value)
                )
        result.append(merged)
    return result


def dedupe_github_contributors(
    contributors: list[ContributorData],
) -> list[ContributorData]:
    if len(contributors) <= 1:
        return contributors

    ids: list[tuple[str, set[str], set[str], int | None]] = [
        _github_id(data) for data in contributors
    ]
    groups: dict[int, list[int]] = ContributorIdResolver(
        obs=[
            ContributorIdObs.create(
                names=authors, emails=emails, login=login, user_id=user_id
            )
            for login, authors, emails, user_id in ids
        ]
    ).groups()

    res: list[ContributorData] = []
    avatar_key: str = enums.RepoPinsResDictKeys.AVATAR_URL.value
    for idxes in groups.values():
        merged: ContributorData = {
            enums.RepoPinsResDictKeys.LOGIN.value: "",
            enums.RepoPinsResDictKeys.AUTHOR.value: set(),
            enums.RepoPinsResDictKeys.EMAIL.value: set(),
            enums.RepoPinsResDictKeys.CONTRIBUTIONS.value: 0,
            enums.RepoPinsResDictKeys.LAST_COMMIT_AT.value: "",
        }
        selected_date: str | None = None
        for idx in idxes:
            data: dict[str, Any] = contributors[idx]
            login, authors, emails, user_id = ids[idx]
            merged[enums.RepoPinsResDictKeys.AUTHOR.value].update(authors)
            merged[enums.RepoPinsResDictKeys.EMAIL.value].update(emails)

            profile_date: str = str(
                data.get(enums.RepoPinsResDictKeys.LAST_COMMIT_AT.value, "") or ""
            )
            if (login or user_id is not None or data.get(avatar_key)) and (
                selected_date is None or profile_date > selected_date
            ):
                selected_date = profile_date
                merged[enums.RepoPinsResDictKeys.LOGIN.value] = str(
                    data.get(enums.RepoPinsResDictKeys.LOGIN.value, "") or ""
                ).strip()
                if user_id is None:
                    merged.pop("id", None)
                else:
                    merged["id"] = user_id
                if avatar_url := data.get(avatar_key):
                    merged[avatar_key] = avatar_url
                else:
                    merged.pop(avatar_key, None)
                merged[enums.RepoPinsResDictKeys.LAST_COMMIT_AT.value] = profile_date

            merged[enums.RepoPinsResDictKeys.CONTRIBUTIONS.value] = max(
                _count(data=merged), _count(data=data)
            )
        res.append(merged)
    return res


def _is_profile_linked(data: ContributorData) -> bool:
    login, _, _, user_id = _github_id(data=data)
    return bool(
        user_id is not None
        or login
        or data.get(enums.RepoPinsResDictKeys.AVATAR_URL.value)
    )


def resolve_repo_contributors(
    repo_data: ContributorData,
    login_username: str,
    login_user_name: str,
    login_user_id: int | None,
) -> ContributorRes:
    contribution_data: list[Any] | Any = (
        repo_data.get(enums.RepoPinsResDictKeys.CONTRIBUTION.value, []) or []
    )
    local_contributors: list[Any] | Any = (
        repo_data.get(enums.RepoPinsResDictKeys.LOCAL_CONTRIBUTORS.value, []) or []
    )
    if not local_contributors:
        local_contributors = [
            data
            for data in contribution_data
            if enums.RepoPinsResDictKeys.STATS.value in data
        ]

    github_contributors: list[Any] | Any = (
        repo_data.get(enums.RepoPinsResDictKeys.CONTRIBUTORS.value, []) or []
    )
    if not github_contributors:
        github_contributors = [
            data
            for data in contribution_data
            if data.get(enums.RepoPinsResDictKeys.AVATAR_URL.value)
        ]

    local_contributors = collapse_local_contributors(local_contributors)
    github_contributors = dedupe_github_contributors(github_contributors)
    local_ids: list[tuple[str, set[str], set[str]]] = [
        _local_id(data) for data in local_contributors
    ]
    github_ids: list[tuple[str, set[str], set[str], int | None]] = [
        _github_id(data) for data in github_contributors
    ]

    obs: list[ContributorIdObs] = []
    srcs: list[tuple[str, int]] = []
    for idx, (_, authors, local_emails) in enumerate[tuple[str, set[str], set[str]]](
        local_ids
    ):
        is_user: bool = _matches_local_user(
            authors=authors,
            emails=local_emails,
            login_username=login_username,
            login_user_name=login_user_name,
            login_user_id=login_user_id,
        )
        obs.append(
            ContributorIdObs.create(
                names=authors,
                emails=local_emails,
                login=login_username if is_user else "",
                user_id=login_user_id if is_user else None,
            )
        )
        srcs.append(("local", idx))

    for idx, (login, authors, github_emails, github_user_id) in enumerate[
        tuple[str, set[str], set[str], int | None]
    ](github_ids):
        obs.append(
            ContributorIdObs.create(
                names=authors,
                emails=github_emails,
                login=login,
                user_id=github_user_id,
            )
        )
        srcs.append(("github", idx))

    if not obs:
        return ContributorRes((), 0, None)

    groups: dict[int, list[int]] = ContributorIdResolver(
        obs=obs, is_mult_profile_merge=True
    ).groups()
    login_username_norm: str = norm_val(val=login_username)
    res: list[ResContributor] = []

    for idxes in groups.values():
        local_idxes: list[int] = [
            srcs[idx][1] for idx in idxes if srcs[idx][0] == "local"
        ]
        github_idxes: list[int] = [
            srcs[idx][1] for idx in idxes if srcs[idx][0] == "github"
        ]

        if local_contributors and not local_idxes:
            continue

        names: set[str] = set()
        emails: set[str] = set()
        local_logins: list[str] = []
        stats: float | int = 0.0
        local_commit_count: int = 0
        is_user = False

        for idx in local_idxes:
            login, authors, local_emails = local_ids[idx]
            names.update(authors)
            emails.update(local_emails)
            if login:
                local_logins.append(login)

            data: Any = local_contributors[idx]
            stats += float(data.get(enums.RepoPinsResDictKeys.STATS.value, 0) or 0)
            local_commit_count += _count(data=data)
            is_user |= _matches_local_user(
                authors=authors,
                emails=local_emails,
                login_username=login_username,
                login_user_name=login_user_name,
                login_user_id=login_user_id,
            )

        selected_profile: tuple[ContributorData, str] | None = None
        github_commit_count: int = 0
        for idx in github_idxes:
            login, authors, github_emails, github_user_id = github_ids[idx]
            names.update(authors)
            emails.update(github_emails)

            data = github_contributors[idx]
            profile_date = str(
                data.get(enums.RepoPinsResDictKeys.LAST_COMMIT_AT.value, "") or ""
            )
            if (login or github_user_id is not None) and (
                selected_profile is None or profile_date > selected_profile[1]
            ):
                selected_profile = data, profile_date

            github_commit_count += _count(data)
            is_user |= bool(login_username_norm and login == login_username_norm)

        github_login: str = ""
        avatar_url: str | None = None
        selected_user_id: int | None = None
        if selected_profile is not None:
            data, _ = selected_profile
            github_login = str(
                data.get(enums.RepoPinsResDictKeys.LOGIN.value, "") or ""
            ).strip()
            raw_user_id: str | None = data.get("id")
            selected_user_id = int(raw_user_id) if raw_user_id is not None else None
            raw_avatar_url: str | None = data.get(
                enums.RepoPinsResDictKeys.AVATAR_URL.value
            )
            avatar_url = str(raw_avatar_url) if raw_avatar_url else None

        login = github_login
        if not login and local_logins:
            login = max(local_logins, key=lambda value: (len(value), value))
        if not login and names:
            login = max(names, key=lambda value: (len(value), value))
        if selected_profile is None and local_idxes:
            profile_login, profile_user_id, profile_avatar_url = _local_profile_hint(
                login=login,
                authors=names,
                emails=emails,
            )
            if profile_login:
                login = profile_login
            if selected_user_id is None:
                selected_user_id = profile_user_id
            if avatar_url is None:
                avatar_url = profile_avatar_url

        if not login:
            login = "unknown"

        res.append(
            ResContributor(
                login=login,
                names=frozenset[str](names),
                emails=frozenset[str](emails),
                user_id=selected_user_id,
                avatar_url=avatar_url,
                stats=stats,
                commit_count=(
                    local_commit_count
                    if bool(local_idxes)
                    and all(
                        enums.RepoPinsResDictKeys.CONTRIBUTIONS.value
                        in local_contributors[idx]
                        for idx in local_idxes
                    )
                    else github_commit_count
                ),
                is_user=is_user,
            )
        )

    res.sort(
        key=lambda contributor: (
            (
                contributor.stats
                if bool(local_contributors)
                else float(contributor.commit_count)
            ),
            contributor.commit_count,
            contributor.login.casefold(),
        ),
        reverse=True,
    )

    user_idx: int | None = next(
        (
            idx
            for idx, contributor in enumerate[ResContributor](res)
            if contributor.is_user
        ),
        None,
    )
    contribution_perc: float | int = 0
    if any(enums.RepoPinsResDictKeys.STATS.value in data for data in contribution_data):
        total_stats: float | int = sum(contributor.stats for contributor in res)
        if total_stats and user_idx is not None:
            contribution_perc = res[user_idx].stats / total_stats * 100

    return ContributorRes(
        contributors=tuple[ResContributor](res),
        contribution_perc=contribution_perc,
        user_idx=user_idx,
    )
