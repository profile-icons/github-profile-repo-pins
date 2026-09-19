from gh_profile_repo_pins.repo_pins_img.repo_pins_img_media import RepoPinImgMedia
from gh_profile_repo_pins.repo_pins_exceptions import RepoPinImageMediaError
import gh_profile_repo_pins.repo_pins_enum as enums
from dataclasses import dataclass
from urllib.parse import urlparse
from typing import Any


@dataclass(frozen=True)
class RepoPinContributor:
    login: str
    img: RepoPinImgMedia


@dataclass(frozen=True)
class RepoPinImgData:
    repo_name: str
    stargazer_count: int
    fork_count: int
    issue_open_count: int
    issue_help_count: int
    pull_request_count: int
    contributor_count: int
    contribution_perc: float | int
    top_contributors: tuple[RepoPinContributor, ...]
    user_top_contributor_idx: int | None
    description: str
    url: str
    primary_language_name: str
    primary_language_color: str
    is_fork: bool | str
    parent: str | None
    is_template: bool
    is_archived: bool
    is_private: bool
    theme: enums.RepoPinsImgThemeName
    bg_img: RepoPinImgMedia | None
    user_img: RepoPinImgMedia

    @classmethod
    def repo_pages_url(cls, url: str) -> str:
        if url:
            url_parsed: list[str] = urlparse(url=url).path.strip("/").split("/")
            if len(url_parsed) == 2:
                owner, repo = url_parsed
                url = f"{owner.lower()}.github.io"
                if repo.lower() not in [url, ".github"]:
                    url += f"/{repo}"
                url = f"https://{url}"
        return url

    @classmethod
    def format_repo_pin_data(
        cls,
        repo_data: dict[str, Any],
        user_repo_owner: str,
        login_username: str,
        login_user_name: str,
        login_user_id: int | None,
        theme_name: (
            enums.RepoPinsImgThemeName | None
        ) = enums.RepoPinsImgThemeName.GITHUB_SOFT,
        bg_img: dict | str | None = None,
    ) -> "RepoPinImgData":
        repo_owner = (
            repo_data.get(enums.RepoPinsResDictKeys.URL.value, "").split("/")[-2]
            if len(repo_data.get(enums.RepoPinsResDictKeys.URL.value, "").split("/"))
            > 1
            else ""
        )
        repo_parent = (
            repo_data.get(enums.RepoPinsResDictKeys.PARENT.value, {}).get(
                enums.RepoPinsResDictKeys.OWNER_REPO.value, ""
            )
            or ""
            if repo_data.get(enums.RepoPinsResDictKeys.PARENT.value, {})
            else None
        )
        primary_language_dict = (
            repo_data.get(enums.RepoPinsResDictKeys.LANGUAGE.value, {}) or {}
        )

        try:
            bg_img_media: RepoPinImgMedia | None = (
                (
                    RepoPinImgMedia(**bg_img)
                    if isinstance(bg_img, dict)
                    else RepoPinImgMedia(img=bg_img)
                )
                if bg_img
                and (
                    isinstance(bg_img, dict)
                    and bg_img.get(enums.RepoPinsResDictKeys.IMG.value)
                    or isinstance(bg_img, str)
                )
                else None
            )
        except ValueError as err:
            raise RepoPinImageMediaError(msg=f"Background image error: {str(err)}")

        contribution_data_list: list[dict] = (
            repo_data.get(enums.RepoPinsResDictKeys.CONTRIBUTION.value, []) or []
        )
        contributions: dict[str, int] = {
            str(data.get(enums.RepoPinsResDictKeys.LOGIN.value, "") or "").strip(): (
                data.get(enums.RepoPinsResDictKeys.STATS.value, 0) or 0
            )
            for data in contribution_data_list
            if str(data.get(enums.RepoPinsResDictKeys.LOGIN.value, "") or "").strip()
        }

        github_contributors: list[dict] = (
            repo_data.get(enums.RepoPinsResDictKeys.CONTRIBUTORS.value, []) or []
        )
        if not github_contributors:
            github_contributors = [
                data
                for data in contribution_data_list
                if data.get(enums.RepoPinsResDictKeys.AVATAR_URL.value)
            ]

        github_contributors = sorted(
            [
                data
                for data in github_contributors
                if str(
                    data.get(enums.RepoPinsResDictKeys.LOGIN.value, "") or ""
                ).strip()
            ],
            key=lambda data: int(
                data.get(enums.RepoPinsResDictKeys.CONTRIBUTIONS.value, 0) or 0
            ),
            reverse=True,
        )
        avatar_contributor_data = [
            data
            for data in github_contributors
            if data.get(enums.RepoPinsResDictKeys.AVATAR_URL.value)
        ]
        top_contributor_data = avatar_contributor_data[:3]
        top_contributors: tuple[RepoPinContributor, ...] = tuple(
            RepoPinContributor(
                login=str(data.get(enums.RepoPinsResDictKeys.LOGIN.value, "")).strip(),
                img=RepoPinImgMedia(
                    img=str(data.get(enums.RepoPinsResDictKeys.AVATAR_URL.value)),
                    opacity=1.0,
                ),
            )
            for data in top_contributor_data
        )
        login_username_norm = (login_username or "").strip().casefold()
        user_top_contributor_idx: int | None = next(
            (
                i
                for i, data in enumerate(avatar_contributor_data)
                if str(data.get(enums.RepoPinsResDictKeys.LOGIN.value, "") or "")
                .strip()
                .casefold()
                == login_username_norm
            ),
            None,
        )

        login_user_name_norm = (login_user_name or "").strip().casefold()
        contribution_perc: float = 0
        total_contributions = sum(contributions.values())
        for contribution_data in contribution_data_list:
            authors = {
                str(author).strip().casefold()
                for author in contribution_data.get(
                    enums.RepoPinsResDictKeys.AUTHOR.value, []
                )
            }
            emails = {
                str(email).strip().casefold()
                for email in contribution_data.get(
                    enums.RepoPinsResDictKeys.EMAIL.value, []
                )
                if email
            }
            account_noreply_email = (
                f"{login_user_id}+{login_username_norm}@users.noreply.github.com"
                if login_user_id is not None
                else ""
            )
            is_user = (
                (bool(login_user_name_norm) and login_user_name_norm in authors)
                or (bool(login_username_norm) and login_username_norm in authors)
                or (bool(account_noreply_email) and account_noreply_email in emails)
                or (
                    login_user_id is not None
                    and any(
                        email.startswith(f"{login_user_id}+")
                        and email.endswith("@users.noreply.github.com")
                        for email in emails
                    )
                )
            )
            if is_user:
                contributor_key = str(
                    contribution_data.get(enums.RepoPinsResDictKeys.LOGIN.value, "")
                    or ""
                ).strip()
                user_contributions: float = contributions.get(contributor_key, 0)
                if total_contributions:
                    contribution_perc = user_contributions / total_contributions * 100
                break

        github_contributor_count = len(
            {
                str(data.get(enums.RepoPinsResDictKeys.LOGIN.value, "") or "")
                .strip()
                .casefold()
                for data in github_contributors
                if str(
                    data.get(enums.RepoPinsResDictKeys.LOGIN.value, "") or ""
                ).strip()
            }
        )
        contributor_count = github_contributor_count or len(contributions)

        return RepoPinImgData(
            repo_name=(
                f"{repo_owner}/"
                if user_repo_owner.lower() != repo_owner.lower()
                else ""
            )
            + repo_data.get(enums.RepoPinsResDictKeys.NAME.value, ""),
            stargazer_count=repo_data.get(enums.RepoPinsResDictKeys.STARS.value, 0)
            or 0,
            fork_count=repo_data.get(enums.RepoPinsResDictKeys.FORK_COUNT.value, 0)
            or 0,
            issue_open_count=(
                repo_data.get(enums.RepoPinsResDictKeys.ISSUES.value, {}) or {}
            ).get(enums.RepoPinsResDictKeys.TTL_COUNT.value, 0)
            or 0,
            issue_help_count=(
                repo_data.get(enums.RepoPinsResDictKeys.ISSUES_HELP.value, {}) or {}
            ).get(enums.RepoPinsResDictKeys.TTL_COUNT.value, 0)
            or 0,
            pull_request_count=(
                repo_data.get(enums.RepoPinsResDictKeys.PULL_REQUESTS.value, {}) or {}
            ).get(enums.RepoPinsResDictKeys.TTL_COUNT.value, 0)
            or 0,
            contributor_count=contributor_count,
            contribution_perc=contribution_perc,
            top_contributors=top_contributors,
            user_top_contributor_idx=user_top_contributor_idx,
            description=repo_data.get(enums.RepoPinsResDictKeys.DESCRIPTION.value, "")
            or "",
            url=(
                repo_data.get(enums.RepoPinsResDictKeys.URL.value, "") or ""
                if not (
                    repo_data.get(enums.RepoPinsResDictKeys.IS_PRIVATE.value, False)
                    or False
                )
                else (
                    str(
                        repo_data.get(enums.RepoPinsResDictKeys.URL_CUSTOM.value, "")
                    ).strip()
                    if urlparse(
                        str(
                            repo_data.get(enums.RepoPinsResDictKeys.URL_CUSTOM.value)
                        ).strip()
                    ).scheme
                    == "https"
                    else cls.repo_pages_url(
                        url=repo_data.get(enums.RepoPinsResDictKeys.URL.value, "") or ""
                    )
                )
            ),
            primary_language_name=primary_language_dict.get(
                enums.RepoPinsResDictKeys.NAME.value, ""
            )
            or "",
            primary_language_color=primary_language_dict.get(
                enums.RepoPinsResDictKeys.COLOR.value, ""
            )
            or "",
            is_fork=repo_data.get(enums.RepoPinsResDictKeys.IS_FORK.value, False) or "",
            parent=repo_parent,
            is_template=repo_data.get(
                enums.RepoPinsResDictKeys.IS_TEMPLATE.value, False
            )
            or False,
            is_archived=repo_data.get(enums.RepoPinsResDictKeys.IS_ARCHIVE.value, False)
            or False,
            is_private=repo_data.get(enums.RepoPinsResDictKeys.IS_PRIVATE.value, False)
            or False,
            theme=(
                theme_name
                if theme_name
                else (
                    enums.RepoPinsImgThemeName.BG_IMG_CONTRAST
                    if bg_img_media
                    else enums.RepoPinsImgThemeName.GITHUB_SOFT
                )
            ),
            bg_img=bg_img_media,
            user_img=RepoPinImgMedia(
                img=f"https://avatars.githubusercontent.com/u/{login_user_id}?v=4",
                opacity=1.0,
            ),
        )

    def __repr__(self) -> str:
        return (
            f"name: {self.repo_name}\n"
            f"type: {"Private" if self.is_private else "Public"}"
            f"{" archive" if self.is_archived else (" template" if self.is_template else "")}"
            f"{"" if not self.is_fork else f"\nforked from {self.parent}"}"
            f"{f"\ndescription: {self.description}" if self.description else ""}"
            f"{f"\nprimary language: ({self.primary_language_color}) {self.primary_language_name}"
            if self.primary_language_name else ""}"
            f"{f"\nstargazers: {self.stargazer_count}" if self.stargazer_count else ""}"
            f"{f"\nforks: {self.fork_count}" if self.fork_count else ""}"
            f"{f"\nissues (open): {self.issue_open_count}" if self.issue_open_count else ""}"
            f"{f"\nissues (open, help wanted): {self.issue_help_count}" if self.issue_help_count else ""}"
            f"{f"\npull requests (open): {self.pull_request_count}" if self.pull_request_count else ""}"
            f"{f"\ncontributors (default branch): {self.contributor_count}" if self.contributor_count else ""}"
            f"{f"\ncontributions (%): {str(round(self.contribution_perc, 2)).rstrip("0").rstrip(".")}" 
            if self.contribution_perc else ""}"
            f"\ntheme: {self.theme.value if self.theme else "None"}"
            f"\nbackground image: {f"\n{str(self.bg_img)}" if self.bg_img else "None\n"}"
            f"\nuser image: {f"\n{str(self.user_img)}" if self.user_img else "None\n"}"
        )
