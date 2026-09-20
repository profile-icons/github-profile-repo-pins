from gh_profile_repo_pins.repo_pins_data.repo_pins_contributors import (
    ResolvedContributor,
    resolve_repo_contributors,
)
from gh_profile_repo_pins.repo_pins_img.repo_pins_img_media import RepoPinImgMedia
from gh_profile_repo_pins.repo_pins_exceptions import RepoPinImageMediaError
import gh_profile_repo_pins.repo_pins_enum as enums
from dataclasses import dataclass
from urllib.parse import urlparse
from typing import Any


@dataclass(frozen=True)
class RepoPinContributor:
    login: str
    img: RepoPinImgMedia | None
    is_user: bool = False
    is_unknown: bool = False


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
            url_parsed: list[str | Any] = urlparse(url=url).path.strip("/").split("/")
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

        contributor_resolution = resolve_repo_contributors(
            repo_data=repo_data,
            login_username=login_username,
            login_user_name=login_user_name,
            login_user_id=login_user_id,
        )
        contributor_count = contributor_resolution.count
        contribution_perc = contributor_resolution.contribution_perc
        user_top_contributor_idx = contributor_resolution.user_idx

        user_img_media = RepoPinImgMedia(
            img=f"https://avatars.githubusercontent.com/u/{login_user_id}?v=4",
            opacity=1.0,
        )

        def contributor_img(
            contributor: ResolvedContributor,
        ) -> RepoPinImgMedia | None:
            if contributor.avatar_url:
                return RepoPinImgMedia(img=contributor.avatar_url, opacity=1.0)
            if contributor.is_user and login_user_id is not None:
                return user_img_media
            return None

        top_entities = list(contributor_resolution.contributors[:4])
        known_top_avatar_count = sum(
            contributor_img(contributor) is not None for contributor in top_entities
        )
        include_unknown_placeholder = (
            known_top_avatar_count in (1, 2, 3)
            and contributor_count > known_top_avatar_count
        )
        top_contributor_list: list[RepoPinContributor] = []
        is_unknown_contributor = False
        for contributor in top_entities:
            img = contributor_img(contributor)
            if img is None:
                if not include_unknown_placeholder or is_unknown_contributor:
                    continue
                is_unknown_contributor = True
                top_contributor_list.append(
                    RepoPinContributor(
                        login=contributor.login,
                        img=None,
                        is_unknown=True,
                    )
                )
                continue
            top_contributor_list.append(
                RepoPinContributor(
                    login=contributor.login,
                    img=img,
                    is_user=contributor.is_user,
                )
            )
        top_contributors = tuple[RepoPinContributor](top_contributor_list)

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
            user_img=user_img_media,
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
