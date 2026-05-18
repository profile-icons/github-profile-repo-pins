from gh_profile_repo_pins.repo_pins_img.repo_pins_img_media import RepoPinImgMedia
from gh_profile_repo_pins.repo_pins_exceptions import RepoPinImageMediaError
import gh_profile_repo_pins.repo_pins_enum as enums
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class RepoPinImgData:
    repo_name: str
    stargazer_count: int
    fork_count: int
    issue_open_count: int
    issue_help_count: int
    pull_request_count: int
    contributor_count: int
    contribution_perc: float
    description: str
    url: str
    primary_language_name: str
    primary_language_color: str
    is_fork: bool
    parent: str
    is_template: bool
    is_archived: bool
    is_private: bool
    theme: enums.RepoPinsImgThemeName
    bg_img: RepoPinImgMedia
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
        repo_data: dict,
        user_repo_owner: str,
        login_username: str,
        login_user_name: str,
        login_user_id: int,
        theme_name: enums.RepoPinsImgThemeName = enums.RepoPinsImgThemeName.GITHUB_SOFT,
        bg_img: dict | str = None,
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
            bg_img = (
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

        contributions: dict[str, int] = {
            data.get(enums.RepoPinsResDictKeys.LOGIN.value).strip(): data.get(
                enums.RepoPinsResDictKeys.STATS.value, 0
            )
            for data in (
                repo_data.get(enums.RepoPinsResDictKeys.CONTRIBUTION.value, []) or []
            )
            if (data.get(enums.RepoPinsResDictKeys.LOGIN.value, "") or "") != ""
        }

        contribution_perc: float = 0
        for contribution_data in (
            repo_data.get(enums.RepoPinsResDictKeys.CONTRIBUTION.value, []) or []
        ):
            if (
                login_user_name  # real name, if using any
                in contribution_data.get(enums.RepoPinsResDictKeys.AUTHOR.value, [])
                or login_username  # username, incase not including a real name or not using it and username instead
                in contribution_data.get(enums.RepoPinsResDictKeys.AUTHOR.value, [])
                or f"{login_user_id}+{login_username}@users.noreply.github.com"  # GitHub email associated with account
                in contribution_data.get(enums.RepoPinsResDictKeys.EMAIL.value, [])
                or any(
                    [
                        email
                        for email in contribution_data.get(
                            enums.RepoPinsResDictKeys.EMAIL.value, []
                        )
                        if email.strip().startswith(f"{login_user_id}+")
                        and email.strip().endswith(
                            "@users.noreply.github.com"
                        )  # if changed name, fallback to ID in email
                    ]
                )
            ):
                user_contributions: float = contributions.get(
                    contribution_data.get(
                        enums.RepoPinsResDictKeys.LOGIN.value
                    ).strip(),
                    0,
                )
                contribution_perc = (
                    user_contributions
                    / sum([v for _, v in contributions.items()])
                    * 100
                )
                break

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
            contributor_count=len(list(contributions.keys())),
            contribution_perc=contribution_perc,
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
                    if bg_img
                    else enums.RepoPinsImgThemeName.GITHUB_SOFT
                )
            ),
            bg_img=bg_img,
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
