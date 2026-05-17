from requests import (
    post,
    Response,
    Session,
    Timeout,
    HTTPError,
    RequestException,
    ConnectionError,
)
from gh_profile_repo_pins.repo_pins_exceptions import GitHubGraphQlClientError
from concurrent.futures import ThreadPoolExecutor, as_completed
import gh_profile_repo_pins.repo_pins_enum as enums
from dataclasses import dataclass
from threading import local, Lock
from http import HTTPStatus
from time import sleep


@dataclass
class GitHubCredentialData:
    username: str
    user_name: str
    user_id: int
    account_creation: str


class GitHubApiClient:

    __GRAPH_QL_URL: str = "https://api.github.com/graphql"
    __GRAPH_QL_REPO_QUERY_NODE_DATA: str = """
      name
      stargazerCount
      forkCount
      issues(states: OPEN) { totalCount }
      issuesHelp: issues(labels: ["help wanted"], states: OPEN) { totalCount }
      pullRequests(states: OPEN) { totalCount }
      owner { login }
      description
      url
      primaryLanguage { name color }
      isFork
      parent { nameWithOwner }
      isTemplate
      isArchived
      isPrivate
      pushedAt
      createdAt
      updatedAt
      homepageUrl
    """
    __GRAPH_QL_RATE_LIMIT_STR: str = """
      rateLimit { cost }
    """
    __GRAPH_QL_REPO_PIN_QUERY_STR: str = f"""
    query ($login: String!, $num: Int!) {{
      {__GRAPH_QL_RATE_LIMIT_STR}
      user(login: $login) {{
        pinnedItems(
          first: $num
          types: [REPOSITORY]
        ) {{
          edges {{
            node {{
              ... on Repository {{
                {__GRAPH_QL_REPO_QUERY_NODE_DATA}
              }}
            }}
          }}
        }}
      }}
    }}
    """
    __GRAPH_QL_REPO_QUERY_PAGINATION: str = """
      pageInfo { hasNextPage endCursor }
    """
    __GRAPH_QL_REPO_OWN_QUERY_STR: str = f"""
    query ($login: String!, $num: Int!, $after: String, $field: RepositoryOrderField!) {{
      {__GRAPH_QL_RATE_LIMIT_STR}
      user(login: $login) {{
        repositories(
          first: $num
          after: $after
          orderBy: {{ field: $field, direction: DESC }}
        ) {{
          {__GRAPH_QL_REPO_QUERY_PAGINATION}
          nodes {{
            {__GRAPH_QL_REPO_QUERY_NODE_DATA}
          }}
        }}
      }}
    }}
    """
    __GRAPH_QL_REPO_CONTRIBUTED_QUERY_STR: str = f"""
    query ($login: String!, $num: Int!, $after: String, $field: RepositoryOrderField!) {{
      {__GRAPH_QL_RATE_LIMIT_STR}
      user(login: $login) {{
        repositoriesContributedTo(
          first: $num
          after: $after
          contributionTypes: [COMMIT]
          orderBy: {{ field: $field, direction: DESC }}
        ) {{
          {__GRAPH_QL_REPO_QUERY_PAGINATION}
          nodes {{
            {__GRAPH_QL_REPO_QUERY_NODE_DATA}
          }}
        }}
      }}
    }}
    """
    __GRAPH_QL_REPO_NAME_QUERY_STR: str = f"""
    query ($owner: String!, $name: String!) {{
      {__GRAPH_QL_RATE_LIMIT_STR}
      repository(owner: $owner, name: $name) {{
        {__GRAPH_QL_REPO_QUERY_NODE_DATA}
      }}
    }}
    """
    __GRAPH_QL_VERIFY_TOKEN_QUERY: str = f"""
    query {{ 
      {__GRAPH_QL_RATE_LIMIT_STR} 
      viewer {{ login }} 
    }}
    """
    __GRAPH_QL_USER_DATA_QUERY: str = f"""
    query($login: String!) {{
      {__GRAPH_QL_RATE_LIMIT_STR}
      user(login: $login) {{
        login
        name
        databaseId
        createdAt
      }}
    }}
    """
    __DEFAULT_TIME_OUT: int = 10
    __DEFAULT_FETCH_LIMIT: int = 100

    __MAX_WORKERS: int = 8

    def __init__(
        self, api_token: str, username: str = None, fetch_limit: int = None
    ) -> None:
        self.__local_thread: local = local()

        self.__api_headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "Connection": "keep-alive",
            "User-Agent": "hf-pr-counter/1.0",
            "Authorization": f"Bearer {api_token}",
        }

        self.__fetch_limit: int = (
            fetch_limit if fetch_limit else self.__DEFAULT_FETCH_LIMIT
        )
        self.__fetch_cost_ttl: int = 0
        self.__fetch_cost_update_lock: Lock = Lock()

        try:
            self.__gh_config_data: GitHubCredentialData = GitHubCredentialData(
                *self.__verify_user(username=username)
            )
        except AssertionError as err:
            raise GitHubGraphQlClientError(msg=f"API authorization error: {err}")

    def __raise_api_fetch_err(
        self, res: Response, exception: type[BaseException] = GitHubGraphQlClientError
    ) -> None:
        raise exception(f"{(res.json().get(enums.RepoPinsResDictKeys.ERROR.value) or {})
            .get(enums.RepoPinsResDictKeys.MESSAGE.value)
            if res.json().get(enums.RepoPinsResDictKeys.ERROR.value)
            else (
                res.json().get(enums.RepoPinsResDictKeys.ERROR.value,[])[0]
                .get(enums.RepoPinsResDictKeys.MESSAGE.value)
                if isinstance(res.json().get(enums.RepoPinsResDictKeys.ERROR.value), list) 
                and res.json().get(enums.RepoPinsResDictKeys.ERROR.value)
                else (
                    res.json().get(enums.RepoPinsResDictKeys.MESSAGE.value) 
                    if res.json().get(enums.RepoPinsResDictKeys.MESSAGE.value) 
                    else "Bad credentials"
                )
            )}")

    def __update_fetch_cost(self, res_json: dict = None) -> None:
        with self.__fetch_cost_update_lock:
            self.__fetch_cost_ttl += (
                (
                    (res_json.get(enums.RepoPinsResDictKeys.DATA.value, {}) or {}).get(
                        enums.RepoPinsResDictKeys.RATE_LIMIT.value, {}
                    )
                    or {}
                ).get(enums.RepoPinsResDictKeys.COST.value, 0)
                or 0
                if res_json
                else 1
            )

    def __post_request(self, body_json: dict) -> dict[str, str | list[str]] | None:
        try:
            res: Response = post(
                self.__GRAPH_QL_URL,
                headers=self.__api_headers,
                json=body_json,
                timeout=self.__DEFAULT_TIME_OUT,
            )
            if res.status_code == HTTPStatus.OK:
                res_json: dict[str, str | list[str]] = res.json()
                if (
                    res_json.get(enums.RepoPinsResDictKeys.ERROR.value)
                    and isinstance(
                        res_json.get(enums.RepoPinsResDictKeys.ERROR.value)[0], dict
                    )
                    and res_json.get(enums.RepoPinsResDictKeys.ERROR.value)[0].get(
                        enums.RepoPinsResDictKeys.MESSAGE.value
                    )
                ):
                    raise Exception(
                        res_json.get(enums.RepoPinsResDictKeys.ERROR.value)[0].get(
                            enums.RepoPinsResDictKeys.MESSAGE.value
                        )
                    )
                self.__update_fetch_cost(res_json=res_json)
                return res_json
            elif res.status_code == HTTPStatus.UNAUTHORIZED or not (
                (res.json().get(enums.RepoPinsResDictKeys.DATA.value) or {}).get(
                    enums.RepoPinsResDictKeys.VIEWER.value
                )
                or {}
            ).get(enums.RepoPinsResDictKeys.LOGIN.value, None):
                self.__raise_api_fetch_err(res=res)
            else:
                self.__raise_api_fetch_err(res=res)
        except Exception as err:
            raise GitHubGraphQlClientError(msg=f"API request error: {err}")

    def __get_user_config(self, username: str) -> tuple[str, int, str]:
        res: dict[str, str | list[str]] = self.__post_request(
            body_json={
                "query": self.__GRAPH_QL_USER_DATA_QUERY,
                "variables": {enums.RepoPinsResDictKeys.LOGIN.value: username},
            }
        )
        return (
            (
                (res.get(enums.RepoPinsResDictKeys.DATA.value) or {}).get(
                    enums.RepoPinsResDictKeys.USER.value
                )
                or {}
            ).get(enums.RepoPinsResDictKeys.NAME.value, ""),
            (
                (res.get(enums.RepoPinsResDictKeys.DATA.value) or {}).get(
                    enums.RepoPinsResDictKeys.USER.value
                )
                or {}
            ).get(enums.RepoPinsResDictKeys.DB_ID.value, 0),
            (
                (res.get(enums.RepoPinsResDictKeys.DATA.value) or {}).get(
                    enums.RepoPinsResDictKeys.USER.value
                )
                or {}
            ).get(enums.RepoPinsResDictKeys.CREATED_AT.value, ""),
        )

    def __verify_user(self, username: str = None) -> tuple[str, str, int, str]:
        res: dict[str, str | list[str]] = self.__post_request(
            body_json={"query": self.__GRAPH_QL_VERIFY_TOKEN_QUERY}
        )
        res_username: str = (
            (
                (res.get(enums.RepoPinsResDictKeys.DATA.value) or {}).get(
                    enums.RepoPinsResDictKeys.VIEWER.value
                )
                or {}
            )
            .get(enums.RepoPinsResDictKeys.LOGIN.value, "")
            .strip()
        )
        if not username:
            username = res_username
        return (username, *self.__get_user_config(username=username))

    def __process_repo_req(
        self, body_json: dict, repo_data_key: str, is_user_data: bool = True
    ) -> dict:
        res_data: dict = (
            self.__post_request(body_json=body_json).get(
                enums.RepoPinsResDictKeys.DATA.value
            )
            or {}
        )
        return (
            res_data.get(enums.RepoPinsResDictKeys.USER.value) or {}
            if is_user_data
            else res_data
        ).get(repo_data_key) or {}

    def __paginate_fetch_repo_data(
        self, body_json: dict, repo_data_key: str, pinned_repo_urls: list
    ) -> list[dict[str, str | int | dict[str, str]]]:
        res_node_data: list[dict[str, str | int | dict[str, str]]] = []
        repo_urls: set[str] = set(pinned_repo_urls)
        after: str | None = None

        while True:
            repo_data: dict = self.__process_repo_req(
                body_json=(
                    body_json["variables"].update({"after": after}) or body_json
                ),
                repo_data_key=repo_data_key,
            )
            for node in repo_data.get("nodes", []):
                if not node:
                    continue
                url: str = node.get(enums.RepoPinsResDictKeys.URL.value, "")
                if url in repo_urls:
                    continue
                repo_urls.add(url)
                res_node_data.append(node)

            if not repo_data.get("pageInfo", {}).get("hasNextPage"):
                break
            after = repo_data.get("pageInfo", {}).get("endCursor")

        return res_node_data

    def __session(self) -> Session:
        if not hasattr(self.__local_thread, Session.__name__.lower()):
            thread_session: Session = Session()
            thread_session.headers.update(self.__api_headers)
            self.__local_thread.session = thread_session
        return self.__local_thread.session

    def __fetch_repo_contribution_data(
        self, repo_owner: str, repo_name: str
    ) -> list | None:
        query_str: str = (
            f"https://api.github.com/repos/{repo_owner}/{repo_name}/contributors"
        )
        session: Session = self.__session()
        contribution_data: list = []
        page: int = 1

        try:
            while True:
                res_data: list = []
                for i in range(self.__DEFAULT_TIME_OUT):
                    res: Response = session.get(
                        url=query_str,
                        headers=self.__api_headers,
                        params={
                            "per_page": self.__DEFAULT_FETCH_LIMIT,
                            "page": page,
                        },
                        timeout=self.__DEFAULT_TIME_OUT,
                    )
                    self.__update_fetch_cost()

                    if res.status_code == HTTPStatus.OK:
                        res_data.extend(res.json() or [])
                        break
                    if res.status_code == HTTPStatus.ACCEPTED:
                        sleep(min(2**i, 30))
                        continue
                    res.raise_for_status()

                if not res_data:
                    break
                contribution_data.extend(res_data)
                page += 1
        except Exception as err:
            raise GitHubGraphQlClientError(msg=f"API request error: {str(err)}")
        return contribution_data

    def __fetch_repos_contribution_data_parallel(self, repos: list[dict]) -> list[dict]:
        raw_contribution_data: dict = {}
        with ThreadPoolExecutor(
            max_workers=min(self.__MAX_WORKERS, max(1, len(repos)))
        ) as thread_pool:
            for i, repo in enumerate(repos):
                raw_contribution_data[
                    thread_pool.submit(
                        self.__fetch_repo_contribution_data,
                        (
                            (
                                repo.get(enums.RepoPinsResDictKeys.OWNER.value, {})
                                or {}
                            ).get(enums.RepoPinsResDictKeys.LOGIN.value, "")
                            or ""
                        ).strip(),
                        (
                            repo.get(enums.RepoPinsResDictKeys.NAME.value, "") or ""
                        ).strip(),
                    )
                ] = i

            for i_complete in as_completed(fs=raw_contribution_data):
                i = raw_contribution_data[i_complete]
                try:
                    repos[i][
                        enums.RepoPinsResDictKeys.CONTRIBUTION.value
                    ] = i_complete.result()
                except (
                    GitHubGraphQlClientError,
                    Timeout,
                    ConnectionError,
                    HTTPError,
                    RequestException,
                ):
                    repos[i][enums.RepoPinsResDictKeys.CONTRIBUTION.value] = []
        return repos

    @property
    def user_id(self) -> int | None:
        return self.__gh_config_data.user_id

    @property
    def user_name(self) -> str:
        return self.__gh_config_data.user_name

    @property
    def username(self) -> str:
        return self.__gh_config_data.username

    @property
    def fetch_cost(self) -> int:
        return self.__fetch_cost_ttl

    def fetch_pinned_repo_data(
        self, num_repos: int = None
    ) -> list[dict[str, str | int | dict | list]]:
        pinned_repos: dict = self.__process_repo_req(
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
        order_field: enums.RepositoryOrderFieldEnum = None,
        pinned_repo_urls: list[str] = None,
        is_contributed: bool = False,
    ) -> list[dict[str, str | int | dict | list]]:
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
            pinned_repo_urls=pinned_repo_urls if pinned_repo_urls else [],
        )

    def fetch_single_repo_data(
        self,
        repo_owner: str = None,
        repo_name: str = None,
    ) -> dict[str, str | int | dict | list]:
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

    def fetch_contributor_stats(self, repo_list: list[dict]) -> list[dict]:
        return self.__fetch_repos_contribution_data_parallel(repos=repo_list)
