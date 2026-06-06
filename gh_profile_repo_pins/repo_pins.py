from gh_profile_repo_pins.repo_pins_exceptions import (
    GitHubGraphQlClientError,
    RepoPinImageThemeError,
    RepoPinImageMediaError,
    RepoPinStatsError,
)
from gh_profile_repo_pins.repo_pins_data.repo_pins_api import GitHubApiClient
from gh_profile_repo_pins.repo_pins_data.repo_pins_stats import RepoPinStats
from gh_profile_repo_pins.utils import set_git_creds, get_logger, Logger
from gh_profile_repo_pins.repo_pins_generate import GenerateRepoPins
import gh_profile_repo_pins.repo_pins_enum as enums
from random import seed, sample
from datetime import datetime


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
    ) -> None:
        self.__log: Logger = get_logger()
        try:
            self.__gh_api_client: GitHubApiClient = GitHubApiClient(
                api_token=api_token, username=username, repo_owner=repo_owner
            )
        except GitHubGraphQlClientError as err:
            self.__log.error(msg=err.msg)
            exit(1)

        set_git_creds(
            user_name=self.__gh_api_client.user_name,
            user_id=self.__gh_api_client.user_id,
        )
        self.__repo_pins: list[dict] = list()
        self.__theme: str | dict | None = theme
        self.__bg_img: dict | str | None = bg_img

        # optional, exclusive list of repos with high priority over other optional configs
        self.__repo_names_exclusive: list[str] = (
            [r.strip() for r in repo_names_exclusive.split(",") if r.strip() != ""]
            if repo_names_exclusive
            else []
        )

        # optional, default overruled if self.__repo_names_exclusive is not None
        self.__max_num_pins: int = min(
            (
                len(self.__repo_names_exclusive)
                if self.__repo_names_exclusive and not max_num_pins
                else (
                    int(max_num_pins) if max_num_pins else self.__DEFAULT_MAX_NUM_PINS
                )
            ),
            self.__LIMIT_MAX_NUM_PINS,
        )
        self.__repo_priority_order: enums.RepositoryOrderFieldEnum | None = (
            enums.RepositoryOrderFieldEnum(
                [
                    e.value
                    for e in list(enums.RepositoryOrderFieldEnum.__members__.values())
                    if e.value.lower() == repo_priority_order.lower()
                ][0]
            )
            if repo_priority_order
            and repo_priority_order.lower()
            in [
                e.value.lower()
                for e in list(enums.RepositoryOrderFieldEnum.__members__.values())
            ]
            else (
                enums.RepositoryOrderFieldEnum.STARGAZERS
                if not self.__repo_names_exclusive
                else None
            )
        )

        # optional, overruled and excluded if self.__repo_names_exclusive is not None
        self.__is_exclude_repos_owned: bool = is_exclude_repos_owned
        self.__is_exclude_repos_contributed: bool = is_exclude_repos_contributed

        self.__user_repo_owner: str = (
            repo_owner if repo_owner else self.__gh_api_client.username
        )

        self.__is_contribution_stats: bool = is_contribution_stats
        self.__repo_stats: RepoPinStats | None = (
            RepoPinStats(gh_token=api_token) if self.__is_contribution_stats else None
        )

    def __order_repos_by_exclusive_preference(self) -> None:
        self.__repo_pins = [
            repo
            for repo in self.__repo_pins
            for explicit_repo in self.__repo_names_exclusive
            if repo.get(enums.RepoPinsResDictKeys.URL.value)
            and repo.get(enums.RepoPinsResDictKeys.URL.value)
            .strip()
            .rstrip("/")
            .lower()
            .endswith(explicit_repo.lower())
        ][: self.__max_num_pins]

    def __order_repos_by_preference(self) -> None:
        if self.__repo_names_exclusive:
            self.__order_repos_by_exclusive_preference()
        if not self.__repo_names_exclusive or self.__repo_priority_order:
            order_field: str = (
                self.__repo_priority_order.value
                if self.__repo_priority_order
                else self.__DEFAULT_ORDER_FIELD.value
            )
            if self.__repo_priority_order is enums.RepositoryOrderFieldEnum.RANDOM:
                today: datetime = datetime.today()
                seed(
                    a=str(self.__gh_api_client.user_id)[5:]
                    + str(today.month)
                    + str(today.day)
                    + str(today.hour)
                )
                self.__repo_pins = sample(
                    population=self.__repo_pins, k=len(self.__repo_pins)
                )[: self.__max_num_pins]
            else:
                self.__repo_pins = sorted(
                    self.__repo_pins,
                    key=lambda d: next(
                        (v for k, v in d.items() if order_field.upper() == k.upper()), 0
                    ),
                    reverse=(
                        True
                        if order_field.upper()
                        != enums.RepositoryOrderFieldEnum.NAME.value.upper()
                        else False
                    ),
                )[: self.__max_num_pins]

    def __generate_readme_pin_grid_display(self) -> None:
        gen_repo_pins: GenerateRepoPins = GenerateRepoPins(
            repo_pins_data=self.__repo_pins,
            user_repo_owner=self.__user_repo_owner,
            login_username=self.__gh_api_client.username.strip().lower(),
            login_user_name=self.__gh_api_client.user_name.strip().lower(),
            login_user_id=self.__gh_api_client.user_id,
            is_org=self.__gh_api_client.is_org,
            theme=self.__theme,
            bg_img=self.__bg_img,
        )
        gen_repo_pins.grid_display()

    def generate(self) -> None:
        try:
            if self.__repo_names_exclusive:
                for owner_repo in self.__repo_names_exclusive:
                    if not any(
                        [
                            d[enums.RepoPinsResDictKeys.URL.value]
                            .lower()
                            .endswith(owner_repo.lower())
                            for d in self.__repo_pins
                            if d.get(enums.RepoPinsResDictKeys.URL.value)
                        ]
                    ):
                        owner, repo = owner_repo.split("/")
                        self.__repo_pins.append(
                            self.__gh_api_client.fetch_single_repo_data(
                                repo_owner=owner,
                                repo_name=repo,
                            )
                        )
            else:
                self.__repo_pins: list[dict[str, str | int | dict]] = (
                    self.__gh_api_client.fetch_pinned_repo_data()
                )
                owned_repos: list[dict[str, str | int | dict]] = []
                contributed_repos: list[dict[str, str | int | dict]] = []
                if (
                    len(self.__repo_pins) < self.__max_num_pins
                    and not self.__is_exclude_repos_owned
                ):
                    owned_repos.extend(
                        self.__gh_api_client.fetch_owned_or_contributed_to_repo_data(
                            order_field=(
                                self.__repo_priority_order
                                if self.__repo_priority_order
                                is not enums.RepositoryOrderFieldEnum.RANDOM
                                else self.__DEFAULT_ORDER_FIELD
                            ),
                            pinned_repo_urls=[
                                d[enums.RepoPinsResDictKeys.URL.value]
                                for d in self.__repo_pins
                            ],
                        )
                    )
                if (
                    len(self.__repo_pins) < self.__max_num_pins
                    and not self.__is_exclude_repos_contributed
                ):
                    contributed_repos.extend(
                        self.__gh_api_client.fetch_owned_or_contributed_to_repo_data(
                            order_field=(
                                self.__repo_priority_order
                                if self.__repo_priority_order
                                is not enums.RepositoryOrderFieldEnum.RANDOM
                                else self.__DEFAULT_ORDER_FIELD
                            ),
                            pinned_repo_urls=[
                                d[enums.RepoPinsResDictKeys.URL.value]
                                for d in self.__repo_pins
                            ],
                            is_contributed=True,
                        )
                    )
                self.__repo_pins.extend(owned_repos)
                self.__repo_pins.extend(contributed_repos)
            self.__order_repos_by_preference()

            if self.__is_contribution_stats and self.__repo_stats:
                self.__repo_pins = self.__repo_stats.fetch_contribution_stats(
                    repo_list=self.__repo_pins
                )
            else:
                self.__repo_pins = self.__gh_api_client.fetch_contributor_stats(
                    repo_list=self.__repo_pins
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
