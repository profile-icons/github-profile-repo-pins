from gh_profile_repo_pins.repo_pins_data.repo_pins_data_contributors import (
    ContributorRes,
    resolve_repo_contributors,
    ResContributor,
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
        if not url:
            return url

        parts = urlparse(url=url).path.strip("/").split(sep="/")
        if len(parts) != 2:
            return url

        owner, repo = parts
        url = f"{owner.lower()}.github.io"
        if repo.lower() not in [url, ".github"]:
            url += f"/{repo}"
        return f"https://{url}"

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
        url_key: str = enums.RepoPinsResDictKeys.URL.value
        repo_url: str = repo_data.get(url_key, "")
        url_parts: list[str] = repo_url.split("/")
        repo_owner: str = url_parts[-2] if len(url_parts) > 1 else ""

        parent_data: dict[str, Any] = repo_data.get(
            enums.RepoPinsResDictKeys.PARENT.value, {}
        )
        repo_parent: str | None = (
            parent_data.get(enums.RepoPinsResDictKeys.OWNER_REPO.value, "") or ""
            if parent_data
            else None
        )
        language: dict[str, str] = (
            repo_data.get(enums.RepoPinsResDictKeys.LANGUAGE.value, {}) or {}
        )

        try:
            bg_img_media: RepoPinImgMedia | None = (
                RepoPinImgMedia(**bg_img)
                if isinstance(bg_img, dict)
                and bg_img
                and bg_img.get(enums.RepoPinsResDictKeys.IMG.value)
                else (
                    RepoPinImgMedia(img=bg_img)
                    if isinstance(bg_img, str) and bg_img
                    else None
                )
            )
        except ValueError as err:
            raise RepoPinImageMediaError(msg=f"Background image error: {str(err)}")

        res: ContributorRes = resolve_repo_contributors(
            repo_data=repo_data,
            login_username=login_username,
            login_user_name=login_user_name,
            login_user_id=login_user_id,
        )
        user_idx: int | None = res.user_idx
        res_user: ResContributor | None = (
            res.contributors[user_idx]
            if user_idx is not None and user_idx < len(res.contributors)
            else None
        )
        user_img_media: RepoPinImgMedia = RepoPinImgMedia(
            img=(
                res_user.avatar_url
                if res_user is not None and res_user.avatar_url
                else f"https://avatars.githubusercontent.com/u/{login_user_id}?v=4"
            ),
            opacity=1.0,
        )

        top_contributors: list[RepoPinContributor] = []
        is_unknown: bool = False
        for contributor in res.contributors[:4]:
            img: RepoPinImgMedia | None = (
                RepoPinImgMedia(img=contributor.avatar_url, opacity=1.0)
                if contributor.avatar_url
                else (
                    user_img_media
                    if contributor.is_user and login_user_id is not None
                    else None
                )
            )
            if img is None:
                if is_unknown:
                    continue
                is_unknown = True
                top_contributors.append(
                    RepoPinContributor(
                        login=contributor.login,
                        img=None,
                        is_unknown=True,
                    )
                )
                continue
            top_contributors.append(
                RepoPinContributor(
                    login=contributor.login,
                    img=img,
                    is_user=contributor.is_user,
                )
            )

        is_private: bool = (
            repo_data.get(enums.RepoPinsResDictKeys.IS_PRIVATE.value, False) or False
        )
        display_url: str = repo_url or ""
        if is_private:
            custom_url: str = str(
                repo_data.get(enums.RepoPinsResDictKeys.URL_CUSTOM.value)
            ).strip()
            display_url = (
                str(
                    repo_data.get(enums.RepoPinsResDictKeys.URL_CUSTOM.value, "")
                ).strip()
                if urlparse(custom_url).scheme == "https"
                else cls.repo_pages_url(url=repo_url or "")
            )

        def total_count(key: enums.RepoPinsResDictKeys) -> int:
            return (repo_data.get(key.value, {}) or {}).get(
                enums.RepoPinsResDictKeys.TTL_COUNT.value, 0
            ) or 0

        return cls(
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
            issue_open_count=total_count(key=enums.RepoPinsResDictKeys.ISSUES),
            issue_help_count=total_count(key=enums.RepoPinsResDictKeys.ISSUES_HELP),
            pull_request_count=total_count(key=enums.RepoPinsResDictKeys.PULL_REQUESTS),
            contributor_count=res.count,
            contribution_perc=res.contribution_perc,
            top_contributors=tuple[RepoPinContributor](top_contributors),
            user_top_contributor_idx=user_idx,
            description=repo_data.get(enums.RepoPinsResDictKeys.DESCRIPTION.value, "")
            or "",
            url=display_url,
            primary_language_name=language.get(enums.RepoPinsResDictKeys.NAME.value, "")
            or "",
            primary_language_color=language.get(
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
            is_private=is_private,
            theme=theme_name
            or (
                enums.RepoPinsImgThemeName.BG_IMG_CONTRAST
                if bg_img_media
                else enums.RepoPinsImgThemeName.GITHUB_SOFT
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
