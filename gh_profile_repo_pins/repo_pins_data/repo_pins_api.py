from requests import (
    post,
    Response,
    Session,
    Timeout,
    HTTPError,
    RequestException,
    ConnectionError,
)
from gh_profile_repo_pins.repo_pins_data.repo_pins_contributor_id import (
    ContributorIdObs,
    ContributorIdResolver,
)
from gh_profile_repo_pins.repo_pins_exceptions import GitHubGraphQlClientError
from concurrent.futures import ThreadPoolExecutor, as_completed
import gh_profile_repo_pins.repo_pins_enum as enums
from dataclasses import dataclass
from threading import local, Lock
from typing import Any, NoReturn
from http import HTTPStatus
from time import sleep


@dataclass
class GitHubCredentialData:
    username: str
    user_name: str
    user_id: int
    account_creation: str
    is_org: bool = False


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
    __GRAPH_QL_REPO_OWNER_TYPE_QUERY: str = f"""
    query ($login: String!) {{
      {__GRAPH_QL_RATE_LIMIT_STR}
      repositoryOwner(login: $login) {{
        __typename
      }}
    }}
    """
    __GRAPH_QL_REPO_COMMIT_AUTHORS_QUERY: str = f"""
    query ($owner: String!, $name: String!, $after: String) {{
      {__GRAPH_QL_RATE_LIMIT_STR}
      repository(owner: $owner, name: $name) {{
        defaultBranchRef {{
          target {{
            ... on Commit {{
              history(first: 100, after: $after) {{
                pageInfo {{ hasNextPage endCursor }}
                nodes {{
                  committedDate
                  parents(first: 2) {{ totalCount }}
                  authors(first: 100) {{
                    nodes {{
                      name
                      email
                      user {{
                        login
                        databaseId
                        avatarUrl
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """
    __DEFAULT_TIME_OUT: int = 10
    __DEFAULT_FETCH_LIMIT: int = 100

    __MAX_WORKERS: int = 8

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

    def __post_request(self, body_json: dict[str, Any]) -> dict[str, Any]:
        try:
            res: Response = post(
                self.__GRAPH_QL_URL,
                headers=self.__api_headers,
                json=body_json,
                timeout=self.__DEFAULT_TIME_OUT,
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

    def __fetch_repo_contribution_data_rest(
        self, repo_owner: str, repo_name: str
    ) -> list[dict[str, Any]]:
        query_str: str = (
            f"https://api.github.com/repos/{repo_owner}/{repo_name}/contributors"
        )
        session: Session = self.__session()
        contribution_data: list[dict[str, Any]] = []
        page: int = 1

        while True:
            page_data: list[dict[str, Any]] = []
            for attempt in range(self.__DEFAULT_TIME_OUT):
                res: Response = session.get(
                    url=query_str,
                    headers=self.__api_headers,
                    params={
                        "anon": 1,
                        "per_page": self.__DEFAULT_FETCH_LIMIT,
                        "page": page,
                    },
                    timeout=self.__DEFAULT_TIME_OUT,
                )
                self.__update_fetch_cost()

                if res.status_code == HTTPStatus.OK:
                    page_data.extend(res.json() or [])
                    break
                if res.status_code == HTTPStatus.ACCEPTED:
                    sleep(min(2**attempt, 30))
                    continue
                res.raise_for_status()

            if not page_data:
                return contribution_data
            contribution_data.extend(page_data)
            page += 1

    def __commit_history(self, res: dict[str, Any]) -> dict[str, Any]:
        return self.__dict_path(
            res,
            enums.RepoPinsResDictKeys.DATA.value,
            "repository",
            "defaultBranchRef",
            "target",
            "history",
        )

    def __author_observation(
        self, actor: dict[str, Any], commit_date: str
    ) -> dict[str, Any] | None:
        user: dict[Any, Any] | Any = actor.get("user") or {}
        login: str = self.__clean(val=user.get(enums.RepoPinsResDictKeys.LOGIN.value))
        db_id: str | None = user.get(enums.RepoPinsResDictKeys.DB_ID.value)
        author_name: str = self.__clean(
            val=actor.get(enums.RepoPinsResDictKeys.NAME.value)
        )
        email: str = self.__clean(val=actor.get(enums.RepoPinsResDictKeys.EMAIL.value))

        if not (login or db_id is not None or author_name or email):
            return None

        obs: dict[str, Any] = {
            enums.RepoPinsResDictKeys.LOGIN.value: login,
            enums.RepoPinsResDictKeys.NAME.value: author_name,
            enums.RepoPinsResDictKeys.EMAIL.value: email,
            enums.RepoPinsResDictKeys.LAST_COMMIT_AT.value: commit_date,
        }
        if db_id is not None:
            obs["id"] = str(db_id)

        avatar_url: str | None = user.get("avatarUrl")
        if avatar_url:
            obs[enums.RepoPinsResDictKeys.AVATAR_URL.value] = str(avatar_url)
        return obs

    def __collect_commit_author_observations(
        self, repo_owner: str, repo_name: str
    ) -> tuple[list[dict[str, Any]], list[list[int]]]:
        obs: list[dict[str, Any]] = []
        commit_obs: list[list[int]] = []
        after: str | None = None

        while True:
            history: dict[str, Any] = self.__commit_history(
                self.__post_request(
                    body_json={
                        "query": self.__GRAPH_QL_REPO_COMMIT_AUTHORS_QUERY,
                        "variables": {
                            "owner": repo_owner,
                            "name": repo_name,
                            "after": after,
                        },
                    }
                )
            )

            for commit in history.get("nodes", []) or []:
                if not commit:
                    continue
                if ((commit.get("parents") or {}).get("totalCount", 0) or 0) > 1:
                    continue

                commit_idxes: list[int] = []
                commit_date: str = str(commit.get("committedDate", "") or "")
                for actor in (commit.get("authors") or {}).get("nodes", []) or []:
                    if not actor:
                        continue
                    auth_obs: dict[str, Any] | None = self.__author_observation(
                        actor=actor,
                        commit_date=commit_date,
                    )
                    if auth_obs is None:
                        continue
                    commit_idxes.append(len(obs))
                    obs.append(auth_obs)

                if commit_idxes:
                    commit_obs.append(commit_idxes)

            page_info: dict[Any, Any] | Any = history.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")
            if not after:
                break

        return obs, commit_obs

    def __resolve_contributors(
        self,
        obs: list[dict[str, Any]],
        commit_obs: list[list[int]],
    ) -> list[dict[str, Any]]:
        roots = ContributorIdResolver(
            obs=[
                ContributorIdObs.create(
                    names={self.__clean(ob.get(enums.RepoPinsResDictKeys.NAME.value))},
                    emails={
                        self.__clean(ob.get(enums.RepoPinsResDictKeys.EMAIL.value))
                    },
                    login=ob.get(enums.RepoPinsResDictKeys.LOGIN.value, ""),
                    user_id=ob.get("id"),
                )
                for ob in obs
            ],
            is_mult_profile_merge=True,
        ).resolve()

        contributors: dict[int, dict[str, Any]] = {}
        for idx, ob in enumerate[dict[str, Any]](obs):
            contributor: dict[str, Any] = contributors.setdefault(
                roots[idx],
                {
                    enums.RepoPinsResDictKeys.LOGIN.value: "",
                    enums.RepoPinsResDictKeys.CONTRIBUTIONS.value: 0,
                    enums.RepoPinsResDictKeys.AUTHOR.value: set(),
                    enums.RepoPinsResDictKeys.EMAIL.value: set(),
                    enums.RepoPinsResDictKeys.LAST_COMMIT_AT.value: "",
                },
            )
            author_name: str = self.__clean(
                ob.get(enums.RepoPinsResDictKeys.NAME.value)
            )
            email: str = self.__clean(ob.get(enums.RepoPinsResDictKeys.EMAIL.value))
            login: str = self.__clean(ob.get(enums.RepoPinsResDictKeys.LOGIN.value))
            commit_date: str = str(
                ob.get(enums.RepoPinsResDictKeys.LAST_COMMIT_AT.value, "") or ""
            )

            if author_name:
                contributor[enums.RepoPinsResDictKeys.AUTHOR.value].add(author_name)
            if email:
                contributor[enums.RepoPinsResDictKeys.EMAIL.value].add(email)

            cur_latest: str = str(
                contributor.get(enums.RepoPinsResDictKeys.LAST_COMMIT_AT.value, "")
                or ""
            )
            if not bool(
                login
                or ob.get("id") is not None
                or ob.get(enums.RepoPinsResDictKeys.AVATAR_URL.value)
            ) or (cur_latest and commit_date < cur_latest):
                continue

            if login:
                contributor[enums.RepoPinsResDictKeys.LOGIN.value] = login
            if ob.get("id") is not None:
                contributor["id"] = ob.get("id")
            avatar_url: str | None = ob.get(enums.RepoPinsResDictKeys.AVATAR_URL.value)
            if avatar_url:
                contributor[enums.RepoPinsResDictKeys.AVATAR_URL.value] = avatar_url
            contributor[enums.RepoPinsResDictKeys.LAST_COMMIT_AT.value] = commit_date

        contribution_key: str = enums.RepoPinsResDictKeys.CONTRIBUTIONS.value
        for commit_indexes in commit_obs:
            for root in {roots[index] for index in commit_indexes}:
                contributor = contributors[root]
                contributor[contribution_key] = (
                    int(contributor.get(contribution_key, 0) or 0) + 1
                )

        return sorted(
            contributors.values(),
            key=lambda data: (
                int(data.get(contribution_key, 0) or 0),
                self.__clean(
                    data.get(enums.RepoPinsResDictKeys.LOGIN.value)
                ).casefold(),
                max(
                    (
                        str(value).casefold()
                        for value in data.get(
                            enums.RepoPinsResDictKeys.AUTHOR.value, set()
                        )
                    ),
                    default="",
                ),
            ),
            reverse=True,
        )

    def __fetch_repo_commit_author_data(
        self, repo_owner: str, repo_name: str
    ) -> list[dict[str, Any]]:
        obs, commit_obs = self.__collect_commit_author_observations(
            repo_owner=repo_owner,
            repo_name=repo_name,
        )
        if not obs:
            return []
        return self.__resolve_contributors(
            obs=obs,
            commit_obs=commit_obs,
        )

    def __fetch_repo_contribution_data(
        self, repo_owner: str, repo_name: str
    ) -> list[dict[str, Any]]:
        try:
            contribution_data: list[dict[str, Any]] = (
                self.__fetch_repo_commit_author_data(
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                )
            )
            if contribution_data:
                return contribution_data
        except GitHubGraphQlClientError:
            pass

        try:
            return self.__fetch_repo_contribution_data_rest(
                repo_owner=repo_owner,
                repo_name=repo_name,
            )
        except Exception as err:
            raise GitHubGraphQlClientError(msg=f"API request error: {str(err)}")

    def __fetch_repos_contribution_data_parallel(
        self, repos: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not repos:
            return repos

        with ThreadPoolExecutor(
            max_workers=min(self.__MAX_WORKERS, len(repos))
        ) as thread_pool:
            futures: dict[Any, Any] = {}
            for idx, repo in enumerate[dict[str, Any]](repos):
                owner: str = self.__clean(
                    (repo.get(enums.RepoPinsResDictKeys.OWNER.value) or {}).get(
                        enums.RepoPinsResDictKeys.LOGIN.value
                    )
                )
                repo_name: str = self.__clean(
                    repo.get(enums.RepoPinsResDictKeys.NAME.value)
                )
                future: Any = thread_pool.submit(
                    self.__fetch_repo_contribution_data,
                    owner,
                    repo_name,
                )
                futures[future] = idx

            for future in as_completed(fs=futures):
                idx = futures[future]
                try:
                    contributor_data: Any = future.result()
                except (
                    GitHubGraphQlClientError,
                    Timeout,
                    ConnectionError,
                    HTTPError,
                    RequestException,
                ):
                    contributor_data = []

                repos[idx][
                    enums.RepoPinsResDictKeys.CONTRIBUTORS.value
                ] = contributor_data
                repos[idx][
                    enums.RepoPinsResDictKeys.CONTRIBUTION.value
                ] = contributor_data

        return repos

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

    def fetch_contributor_stats(
        self, repo_list: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return self.__fetch_repos_contribution_data_parallel(repos=repo_list)
