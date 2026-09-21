from gh_profile_repo_pins.repo_pins_exceptions import (
    GitHubGraphQlClientError,
    RepoPinImageMediaError,
    RepoPinImageThemeError,
    RepoPinStatsError,
)
from gh_profile_repo_pins.repo_pins_data.repo_pins_api import GitHubApiClient
from gh_profile_repo_pins.repo_pins_data.repo_pins_stats import RepoPinStats
from gh_profile_repo_pins.repo_pins_generate import GenerateRepoPins
from utils.utils import Logger, get_logger, set_git_creds
import gh_profile_repo_pins.repo_pins_enum as enums
from random import sample, seed
from datetime import datetime
from typing import Any


class ReadMeRepoPins:

    __DEFAULT_MAX_NUM_PINS: int = 6
    __LIMIT_MAX_NUM_PINS: int = 100
    __DEFAULT_ORDER_FIELD: enums.RepositoryOrderFieldEnum = (
        enums.RepositoryOrderFieldEnum.STARGAZERS
    )

    def __init__(
        self,
        api_token: str,
        username: str | None = None,
        repo_names_exclusive: str | None = None,
        theme: str | dict | None = None,
        bg_img: dict | str | None = None,
        max_num_pins: int | None = None,
        repo_priority_order: str | None = None,
        is_exclude_repos_owned: bool = False,
        is_exclude_repos_contributed: bool = False,
        repo_owner: str | None = None,
        is_contribution_stats: bool = False,
        is_translate: bool = False,
        is_nllb_trans: bool = False,
    ) -> None:
        self.__log: Logger = get_logger()
        try:
            self.__gh_api_client: GitHubApiClient = GitHubApiClient(
                api_token=api_token,
                username=username,
                repo_owner=repo_owner,
            )
        except GitHubGraphQlClientError as err:
            self.__log.error(msg=err.msg)
            exit(1)

        set_git_creds(
            user_name=self.__gh_api_client.user_name,
            user_id=self.__gh_api_client.user_id,
        )
        self.__repo_pins: list[dict[str, str]] = []
        self.__theme: str | dict | None = theme
        self.__bg_img: dict | str | None = bg_img

        self.__repo_names_exclusive: list[str] = (
            [repo.strip() for repo in repo_names_exclusive.split(",") if repo.strip()]
            if repo_names_exclusive
            else []
        )
        default_pin_count: int = (
            len(self.__repo_names_exclusive)
            if self.__repo_names_exclusive and not max_num_pins
            else int(max_num_pins) if max_num_pins else self.__DEFAULT_MAX_NUM_PINS
        )
        self.__max_num_pins: int = min(default_pin_count, self.__LIMIT_MAX_NUM_PINS)

        default_order: enums.RepositoryOrderFieldEnum | None = (
            self.__DEFAULT_ORDER_FIELD if not self.__repo_names_exclusive else None
        )
        self.__repo_priority_order: enums.RepositoryOrderFieldEnum | None = (
            next(
                (
                    field
                    for field in enums.RepositoryOrderFieldEnum.__members__.values()
                    if field.value.lower() == repo_priority_order.lower()
                ),
                default_order,
            )
            if repo_priority_order
            else default_order
        )

        self.__is_exclude_repos_owned: bool = is_exclude_repos_owned
        self.__is_exclude_repos_contributed: bool = is_exclude_repos_contributed
        self.__user_repo_owner: str = repo_owner or self.__gh_api_client.username
        self.__is_contribution_stats: bool = is_contribution_stats
        self.__repo_stats: RepoPinStats = RepoPinStats(gh_token=api_token)
        self.__is_translate: bool = is_translate
        self.__is_nllb_trans: bool = is_nllb_trans

    def __order_repos_by_exclusive_preference(self) -> None:
        self.__repo_pins = [
            repo
            for repo in self.__repo_pins
            for explicit_repo in self.__repo_names_exclusive
            if isinstance(
                repo_url := repo.get(enums.RepoPinsResDictKeys.URL.value), str
            )
            and repo_url.strip().rstrip("/").lower().endswith(explicit_repo.lower())
        ][: self.__max_num_pins]

    def __order_repos_by_preference(self) -> None:
        if self.__repo_names_exclusive:
            self.__order_repos_by_exclusive_preference()
        if self.__repo_names_exclusive and not self.__repo_priority_order:
            return

        order_field: str = (
            self.__repo_priority_order or self.__DEFAULT_ORDER_FIELD
        ).value
        if self.__repo_priority_order is enums.RepositoryOrderFieldEnum.RANDOM:
            today: datetime = datetime.today()
            seed(
                a=str(self.__gh_api_client.user_id)[5:]
                + str(today.month)
                + str(today.day)
                + str(today.hour)
            )
            self.__repo_pins = sample(
                population=self.__repo_pins,
                k=len(self.__repo_pins),
            )[: self.__max_num_pins]
            return

        self.__repo_pins = sorted(
            self.__repo_pins,
            key=lambda repo: next(
                (
                    val
                    for key, val in repo.items()
                    if order_field.upper() == key.upper()
                ),
                0,
            ),
            reverse=(
                order_field.upper() != enums.RepositoryOrderFieldEnum.NAME.value.upper()
            ),
        )[: self.__max_num_pins]

    def __generate_readme_pin_grid_display(self) -> None:
        GenerateRepoPins(
            repo_pins_data=self.__repo_pins,
            user_repo_owner=self.__user_repo_owner,
            login_username=self.__gh_api_client.username.strip().lower(),
            login_user_name=self.__gh_api_client.user_name.strip().lower(),
            login_user_id=self.__gh_api_client.user_id,
            is_org=self.__gh_api_client.is_org,
            theme=self.__theme,
            bg_img=self.__bg_img,
            is_translate=self.__is_translate,
            is_nllb_trans=self.__is_nllb_trans,
        ).grid_display()

    def generate(self) -> None:
        try:
            if self.__repo_names_exclusive:
                for owner_repo in self.__repo_names_exclusive:
                    if not any(
                        repo[enums.RepoPinsResDictKeys.URL.value]
                        .lower()
                        .endswith(owner_repo.lower())
                        for repo in self.__repo_pins
                        if repo.get(enums.RepoPinsResDictKeys.URL.value)
                    ):
                        owner, repo = owner_repo.split("/")
                        self.__repo_pins.append(
                            self.__gh_api_client.fetch_single_repo_data(
                                repo_owner=owner,
                                repo_name=repo,
                            )
                        )
            else:
                self.__repo_pins = self.__gh_api_client.fetch_pinned_repo_data()
                owned_repos: list[dict[str, Any]] = []
                contributed_repos: list[dict[str, Any]] = []

                if len(self.__repo_pins) < self.__max_num_pins:
                    order_field: enums.RepositoryOrderFieldEnum = (
                        self.__repo_priority_order
                        if self.__repo_priority_order
                        and self.__repo_priority_order
                        is not enums.RepositoryOrderFieldEnum.RANDOM
                        else self.__DEFAULT_ORDER_FIELD
                    )
                    pinned_urls: list[str] = [
                        repo[enums.RepoPinsResDictKeys.URL.value]
                        for repo in self.__repo_pins
                    ]
                    if not self.__is_exclude_repos_owned:
                        owned_repos = self.__gh_api_client.fetch_owned_or_contributed_to_repo_data(
                            order_field=order_field,
                            pinned_repo_urls=pinned_urls,
                        )
                    if not self.__is_exclude_repos_contributed:
                        contributed_repos = self.__gh_api_client.fetch_owned_or_contributed_to_repo_data(
                            order_field=order_field,
                            pinned_repo_urls=pinned_urls,
                            is_contributed=True,
                        )

                self.__repo_pins.extend(owned_repos)
                self.__repo_pins.extend(contributed_repos)

            self.__order_repos_by_preference()
            self.__repo_pins = self.__gh_api_client.fetch_contributor_stats(
                repo_list=self.__repo_pins
            )
            self.__repo_pins = self.__repo_stats.fetch_contribution_stats(
                repo_list=self.__repo_pins,
                is_percentage_stats=self.__is_contribution_stats,
                raise_errors=self.__is_contribution_stats,
            )
            self.__log.info(
                msg=f"Total API fetch cost: {self.__gh_api_client.fetch_cost}"
            )
        except (GitHubGraphQlClientError, RepoPinStatsError) as err:
            self.__log.error(msg=err.msg)
            exit(1)

        try:
            self.__generate_readme_pin_grid_display()
        except (RepoPinImageThemeError, RepoPinImageMediaError) as err:
            self.__log.error(msg=err.msg)
            exit(1)
