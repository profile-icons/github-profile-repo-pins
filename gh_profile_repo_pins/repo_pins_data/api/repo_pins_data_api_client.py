from gh_profile_repo_pins.repo_pins_data.api.repo_pins_data_api_contributors import (
    GitHubApiContributors,
)
from gh_profile_repo_pins.repo_pins_data.api.repo_pins_data_api_profiles import (
    GitHubApiProfiles,
)
import gh_profile_repo_pins.repo_pins_data.api.repo_pins_data_api_queries as queries
from gh_profile_repo_pins.repo_pins_exceptions import GitHubGraphQlClientError
import gh_profile_repo_pins.repo_pins_enum as enums
from requests import post, Response, Session
from dataclasses import dataclass
from threading import local, Lock
from typing import Any, NoReturn
from http import HTTPStatus


@dataclass
class GitHubCredentialData:
    username: str
    user_name: str
    user_id: int
    account_creation: str
    is_org: bool = False


class GitHubApiClient:

    __GRAPH_QL_URL: str = queries.GRAPH_QL_URL
    # __GRAPH_QL_REPO_QUERY_NODE_DATA: str = queries.GRAPH_QL_REPO_QUERY_NODE_DATA
    __GRAPH_QL_REPO_PIN_QUERY_STR: str = queries.GRAPH_QL_REPO_PIN_QUERY_STR
    # __GRAPH_QL_REPO_QUERY_PAGINATION: str = queries.GRAPH_QL_REPO_QUERY_PAGINATION
    __GRAPH_QL_REPO_OWN_QUERY_STR: str = queries.GRAPH_QL_REPO_OWN_QUERY_STR
    __GRAPH_QL_REPO_CONTRIBUTED_QUERY_STR: str = (
        queries.GRAPH_QL_REPO_CONTRIBUTED_QUERY_STR
    )
    __GRAPH_QL_REPO_NAME_QUERY_STR: str = queries.GRAPH_QL_REPO_NAME_QUERY_STR
    __GRAPH_QL_VERIFY_TOKEN_QUERY: str = queries.GRAPH_QL_VERIFY_TOKEN_QUERY
    __GRAPH_QL_USER_DATA_QUERY: str = queries.GRAPH_QL_USER_DATA_QUERY
    __GRAPH_QL_REPO_OWNER_TYPE_QUERY: str = queries.GRAPH_QL_REPO_OWNER_TYPE_QUERY
    __DEFAULT_TIME_OUT: int = queries.DEFAULT_TIME_OUT
    __DEFAULT_FETCH_LIMIT: int = queries.DEFAULT_FETCH_LIMIT
    __MAX_WORKERS: int = queries.MAX_WORKERS

    def __init__(
        self,
        api_token: str,
        username: str | None = None,
        repo_owner: str | None = None,
        fetch_limit: int | None = None,
    ) -> None:
        self.__local_thread: local = local()
        self.__api_headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "Connection": "keep-alive",
            "User-Agent": "hf-pr-counter/1.0",
            "Authorization": f"Bearer {api_token}",
        }
        self.__fetch_limit: int = fetch_limit or self.__DEFAULT_FETCH_LIMIT
        self.__fetch_cost_ttl: int = 0
        self.__fetch_cost_update_lock: Lock = Lock()
        self.__contributor_api: GitHubApiContributors = GitHubApiContributors(
            post_request=self.__post_request,
            update_fetch_cost=self.__update_fetch_cost,
            session=self.__session,
            clean=self.__clean,
            dict_path=self.__dict_path,
            api_headers=self.__api_headers,
            default_time_out=self.__DEFAULT_TIME_OUT,
            default_fetch_limit=self.__DEFAULT_FETCH_LIMIT,
            max_workers=self.__MAX_WORKERS,
        )
        self.__profile_api: GitHubApiProfiles = GitHubApiProfiles(
            post_request=self.__post_request,
            author_obs=self.__contributor_api.author_obs,
            resolve_contributors=self.__contributor_api.resolve_contributors,
            dict_path=self.__dict_path,
        )

        try:
            self.__gh_config_data: GitHubCredentialData = GitHubCredentialData(
                *self.__verify_user(username=username)
            )
        except AssertionError as err:
            raise GitHubGraphQlClientError(msg=f"API authorization error: {err}")

        self.__gh_config_data.is_org = (
            self.__get_repo_owner_type(repo_owner=repo_owner)
            == enums.RepoPinsResDictKeys.ORGANIZATION.value
        )

    @staticmethod
    def __dict_path(data: dict[str, Any], *keys: str) -> dict[str, Any]:
        cur: Any = data
        for key in keys:
            cur = cur.get(key) or {}
        return cur

    @staticmethod
    def __clean(val: Any) -> str:
        return str(val or "").strip()

    @staticmethod
    def __raise_api_fetch_err(
        res: Response, exception: type[BaseException] = GitHubGraphQlClientError
    ) -> NoReturn:
        payload: Any = res.json()
        errs: Any = payload.get(enums.RepoPinsResDictKeys.ERROR.value)
        msg: str | None = (
            (errs or {}).get(enums.RepoPinsResDictKeys.MESSAGE.value)
            if errs
            else payload.get(enums.RepoPinsResDictKeys.MESSAGE.value)
            or "Bad credentials"
        )
        raise exception(f"{msg}")

    def __update_fetch_cost(self, res_json: dict | None = None) -> None:
        if not res_json:
            return
        rate_limit: dict[str, Any] = self.__dict_path(
            res_json,
            enums.RepoPinsResDictKeys.DATA.value,
            enums.RepoPinsResDictKeys.RATE_LIMIT.value,
        )
        with self.__fetch_cost_update_lock:
            self.__fetch_cost_ttl += (
                rate_limit.get(enums.RepoPinsResDictKeys.COST.value, 0) or 0
            )

    def __post_request(
        self, body_json: dict[str, Any], timeout: float | int | None = None
    ) -> dict[str, Any]:
        try:
            res: Response = post(
                self.__GRAPH_QL_URL,
                headers=self.__api_headers,
                json=body_json,
                timeout=(timeout if timeout is not None else self.__DEFAULT_TIME_OUT),
            )
            if res.status_code != HTTPStatus.OK:
                self.__raise_api_fetch_err(res=res)

            res_json: dict[str, Any] = res.json()
            errs: Any | None = res_json.get(enums.RepoPinsResDictKeys.ERROR.value)
            if isinstance(errs, list) and errs and isinstance(errs[0], dict):
                err_msg: Any = errs[0].get(enums.RepoPinsResDictKeys.MESSAGE.value)
                if err_msg:
                    raise Exception(err_msg)

            self.__update_fetch_cost(res_json=res_json)
            return res_json
        except Exception as err:
            raise GitHubGraphQlClientError(msg=f"API request error: {err}")

    def __get_user_config(self, username: str) -> tuple[str, int, str]:
        user: dict[str, Any] = self.__dict_path(
            self.__post_request(
                body_json={
                    "query": self.__GRAPH_QL_USER_DATA_QUERY,
                    "variables": {enums.RepoPinsResDictKeys.LOGIN.value: username},
                }
            ),
            enums.RepoPinsResDictKeys.DATA.value,
            enums.RepoPinsResDictKeys.USER.value,
        )
        return (
            user.get(enums.RepoPinsResDictKeys.NAME.value, ""),
            user.get(enums.RepoPinsResDictKeys.DB_ID.value, 0),
            user.get(enums.RepoPinsResDictKeys.CREATED_AT.value, ""),
        )

    def __verify_user(self, username: str | None = None) -> tuple[str, str, int, str]:
        viewer: dict[str, Any] = self.__dict_path(
            self.__post_request(
                body_json={"query": self.__GRAPH_QL_VERIFY_TOKEN_QUERY}
            ),
            enums.RepoPinsResDictKeys.DATA.value,
            enums.RepoPinsResDictKeys.VIEWER.value,
        )
        verified_username: str = self.__clean(
            viewer.get(enums.RepoPinsResDictKeys.LOGIN.value)
        )
        username = username or verified_username
        return username, *self.__get_user_config(username=username)

    def __get_repo_owner_type(self, repo_owner: str | None) -> str:
        assert repo_owner
        owner: dict[str, Any] = self.__dict_path(
            self.__post_request(
                body_json={
                    "query": self.__GRAPH_QL_REPO_OWNER_TYPE_QUERY,
                    "variables": {enums.RepoPinsResDictKeys.LOGIN.value: repo_owner},
                }
            ),
            enums.RepoPinsResDictKeys.DATA.value,
            enums.RepoPinsResDictKeys.REPOSITORY_OWNER.value,
        )
        return self.__clean(owner.get(enums.RepoPinsResDictKeys.TYPENAME.value)).lower()

    def __process_repo_req(
        self, body_json: dict[str, Any], repo_data_key: str, is_user_data: bool = True
    ) -> dict[str, Any]:
        res_data: dict[Any, Any] | Any = (
            self.__post_request(body_json=body_json).get(
                enums.RepoPinsResDictKeys.DATA.value
            )
            or {}
        )
        parent: dict[Any, Any] | Any = (
            res_data.get(enums.RepoPinsResDictKeys.USER.value) or {}
            if is_user_data
            else res_data
        )
        return parent.get(repo_data_key) or {}

    def __paginate_fetch_repo_data(
        self, body_json: dict[str, Any], repo_data_key: str, pinned_repo_urls: list[str]
    ) -> list[dict[str, Any]]:
        res: list[dict[str, Any]] = []
        seen_urls: set[str] = set(pinned_repo_urls)
        after: str | None = None

        while True:
            body_json["variables"]["after"] = after
            repo_data: dict[str, Any] = self.__process_repo_req(
                body_json=body_json,
                repo_data_key=repo_data_key,
            )
            for node in repo_data.get("nodes", []):
                if not node:
                    continue
                url: Any = node.get(enums.RepoPinsResDictKeys.URL.value, "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                res.append(node)

            page_info: Any = repo_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                return res
            after = page_info.get("endCursor")

    def __session(self) -> Session:
        session = getattr(self.__local_thread, "session", None)
        if session is None:
            session = Session()
            session.headers.update(self.__api_headers)
            self.__local_thread.session = session
        return session

    def __fetch_repos_contribution_data_parallel(
        self,
        repos: list[dict[str, Any]],
        max_hist_pages: int | None = None,
        is_rest_fb: bool = True,
    ) -> list[dict[str, Any]]:
        return self.__contributor_api.fetch_repos_contribution_data_parallel(
            repos=repos,
            max_hist_pages=max_hist_pages,
            is_rest_fb=is_rest_fb,
        )

    @property
    def user_id(self) -> int:
        return self.__gh_config_data.user_id

    @property
    def user_name(self) -> str:
        return self.__gh_config_data.user_name

    @property
    def username(self) -> str:
        return self.__gh_config_data.username

    @property
    def is_org(self) -> bool:
        return self.__gh_config_data.is_org

    @property
    def fetch_cost(self) -> int:
        return self.__fetch_cost_ttl

    def fetch_pinned_repo_data(
        self, num_repos: int | None = None
    ) -> list[dict[str, Any]]:
        pinned_repos: dict[str, Any] = self.__process_repo_req(
            body_json={
                "query": self.__GRAPH_QL_REPO_PIN_QUERY_STR,
                "variables": {
                    enums.RepoPinsResDictKeys.LOGIN.value: self.__gh_config_data.username,
                    "num": num_repos if num_repos else self.__fetch_limit,
                },
            },
            repo_data_key="pinnedItems",
        )
        return [edge["node"] for edge in pinned_repos.get("edges", [])]

    def fetch_owned_or_contributed_to_repo_data(
        self,
        order_field: enums.RepositoryOrderFieldEnum | None = None,
        pinned_repo_urls: list[str] | None = None,
        is_contributed: bool = False,
    ) -> list[dict[str, Any]]:
        return self.__paginate_fetch_repo_data(
            body_json={
                "query": (
                    self.__GRAPH_QL_REPO_CONTRIBUTED_QUERY_STR
                    if is_contributed
                    else self.__GRAPH_QL_REPO_OWN_QUERY_STR
                ),
                "variables": {
                    enums.RepoPinsResDictKeys.LOGIN.value: self.__gh_config_data.username,
                    "num": self.__fetch_limit,
                    "field": (
                        order_field.name
                        if order_field
                        else enums.RepositoryOrderFieldEnum.STARGAZERS.name
                    ).upper(),
                },
            },
            repo_data_key=(
                "repositoriesContributedTo" if is_contributed else "repositories"
            ),
            pinned_repo_urls=pinned_repo_urls or [],
        )

    def fetch_single_repo_data(
        self,
        repo_owner: str | None = None,
        repo_name: str | None = None,
    ) -> dict[str, Any]:
        return self.__process_repo_req(
            body_json={
                "query": self.__GRAPH_QL_REPO_NAME_QUERY_STR,
                "variables": {
                    enums.RepoPinsResDictKeys.LOGIN.value: self.__gh_config_data.username,
                    enums.RepoPinsResDictKeys.OWNER.value: repo_owner,
                    enums.RepoPinsResDictKeys.NAME.value: repo_name,
                },
            },
            repo_data_key="repository",
            is_user_data=False,
        )

    def get_contributor_profiles(
        self,
        repo_list: list[dict[str, Any]],
        timeout: float | int = 3.0,
        max_commits_per_repo: int = 24,
    ) -> list[dict[str, Any]]:
        return self.__profile_api.get_contributor_profiles(
            repo_list=repo_list,
            timeout=timeout,
            max_commits_per_repo=max_commits_per_repo,
        )

    def fetch_contributor_stats(
        self,
        repo_list: list[dict[str, Any]],
        max_hist_pages: int | None = None,
        is_rest_fb: bool = True,
    ) -> list[dict[str, Any]]:
        return self.__fetch_repos_contribution_data_parallel(
            repos=repo_list,
            max_hist_pages=max_hist_pages,
            is_rest_fb=is_rest_fb,
        )
