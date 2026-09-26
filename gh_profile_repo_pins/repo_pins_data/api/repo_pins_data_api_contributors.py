from requests import (
    ConnectionError,
    HTTPError,
    RequestException,
    Response,
    Session,
    Timeout,
)
from gh_profile_repo_pins.repo_pins_data.repo_pins_data_contributor_id import (
    ContributorIdObs,
    ContributorIdResolver,
)
import gh_profile_repo_pins.repo_pins_data.api.repo_pins_data_api_queries as queries
from gh_profile_repo_pins.repo_pins_exceptions import GitHubGraphQlClientError
from concurrent.futures import ThreadPoolExecutor, as_completed
import gh_profile_repo_pins.repo_pins_enum as enums
from typing import Any, Callable
from http import HTTPStatus
from time import sleep


class GitHubApiContributors:

    __GRAPH_QL_REPO_COMMIT_AUTHORS_QUERY: str = (
        queries.GRAPH_QL_REPO_COMMIT_AUTHORS_QUERY
    )

    def __init__(
        self,
        post_request: Callable[..., dict[str, Any]],
        update_fetch_cost: Callable[[dict | None], None],
        session: Callable[[], Session],
        clean: Callable[[Any], str],
        dict_path: Callable[..., dict[str, Any]],
        api_headers: dict[str, str],
        default_time_out: int,
        default_fetch_limit: int,
        max_workers: int,
    ) -> None:
        self.__post_request: Callable[..., dict[str, Any]] = post_request
        self.__update_fetch_cost: Callable[[dict | None], None] = update_fetch_cost
        self.__session: Callable[[], Session] = session
        self.__clean: Callable[[Any], str] = clean
        self.__dict_path: Callable[..., dict[str, Any]] = dict_path
        self.__api_headers: dict[str, str] = api_headers
        self.__default_time_out: int = default_time_out
        self.__default_fetch_limit: int = default_fetch_limit
        self.__max_workers: int = max_workers

    def fetch_repo_contribution_data_rest(
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
            for attempt in range(self.__default_time_out):
                res: Response = session.get(
                    url=query_str,
                    headers=self.__api_headers,
                    params={
                        "anon": 1,
                        "per_page": self.__default_fetch_limit,
                        "page": page,
                    },
                    timeout=self.__default_time_out,
                )
                self.__update_fetch_cost(None)

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

    def commit_history(self, res: dict[str, Any]) -> dict[str, Any]:
        return self.__dict_path(
            res,
            enums.RepoPinsResDictKeys.DATA.value,
            "repository",
            "defaultBranchRef",
            "target",
            "history",
        )

    def author_obs(
        self, actor: dict[str, Any], commit_date: str
    ) -> dict[str, Any] | None:
        user: dict[Any, Any] | Any = actor.get("user") or {}
        login: str = self.__clean(user.get(enums.RepoPinsResDictKeys.LOGIN.value))
        db_id: str | None = user.get(enums.RepoPinsResDictKeys.DB_ID.value)
        author_name: str = self.__clean(actor.get(enums.RepoPinsResDictKeys.NAME.value))
        email: str = self.__clean(actor.get(enums.RepoPinsResDictKeys.EMAIL.value))

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

    def collect_commit_author_obs(
        self, repo_owner: str, repo_name: str, max_pages: int | None = None
    ) -> tuple[list[dict[str, Any]], list[list[int]]]:
        obs: list[dict[str, Any]] = []
        commit_obs: list[list[int]] = []
        after: str | None = None
        page_count: int = 0

        while True:
            history: dict[str, Any] = self.commit_history(
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
                    auth_obs: dict[str, Any] | None = self.author_obs(
                        actor=actor,
                        commit_date=commit_date,
                    )
                    if auth_obs is None:
                        continue
                    commit_idxes.append(len(obs))
                    obs.append(auth_obs)

                if commit_idxes:
                    commit_obs.append(commit_idxes)

            page_count += 1
            page_info: dict[Any, Any] | Any = history.get("pageInfo") or {}
            if (max_pages is not None and page_count >= max_pages) or not page_info.get(
                "hasNextPage"
            ):
                break
            after = page_info.get("endCursor")
            if not after:
                break

        return obs, commit_obs

    def resolve_contributors(
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

    def fetch_repo_commit_author_data(
        self, repo_owner: str, repo_name: str, max_pages: int | None = None
    ) -> list[dict[str, Any]]:
        obs, commit_obs = self.collect_commit_author_obs(
            repo_owner=repo_owner,
            repo_name=repo_name,
            max_pages=max_pages,
        )
        if not obs:
            return []
        return self.resolve_contributors(
            obs=obs,
            commit_obs=commit_obs,
        )

    def fetch_repo_contribution_data(
        self,
        repo_owner: str,
        repo_name: str,
        max_history_pages: int | None = None,
        allow_rest_fallback: bool = True,
    ) -> list[dict[str, Any]]:
        try:
            contribution_data: list[dict[str, Any]] = (
                self.fetch_repo_commit_author_data(
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    max_pages=max_history_pages,
                )
            )
            if contribution_data:
                return contribution_data
        except GitHubGraphQlClientError:
            if not allow_rest_fallback:
                return []

        if not allow_rest_fallback:
            return []

        try:
            return self.fetch_repo_contribution_data_rest(
                repo_owner=repo_owner,
                repo_name=repo_name,
            )
        except Exception as err:
            raise GitHubGraphQlClientError(msg=f"API request error: {str(err)}")

    def fetch_repos_contribution_data_parallel(
        self,
        repos: list[dict[str, Any]],
        max_hist_pages: int | None = None,
        is_rest_fb: bool = True,
    ) -> list[dict[str, Any]]:
        if not repos:
            return repos

        with ThreadPoolExecutor(
            max_workers=min(self.__max_workers, len(repos))
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
                    self.fetch_repo_contribution_data,
                    owner,
                    repo_name,
                    max_hist_pages,
                    is_rest_fb,
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

    def fetch_contributor_stats(
        self,
        repo_list: list[dict[str, Any]],
        max_hist_pages: int | None = None,
        is_rest_fb: bool = True,
    ) -> list[dict[str, Any]]:
        return self.fetch_repos_contribution_data_parallel(
            repos=repo_list,
            max_hist_pages=max_hist_pages,
            is_rest_fb=is_rest_fb,
        )
