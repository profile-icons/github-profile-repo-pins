from gh_profile_repo_pins.repo_pins_data.repo_pins_data_contributors import _local_id
import gh_profile_repo_pins.repo_pins_data.api.repo_pins_data_api_queries as queries
from gh_profile_repo_pins.repo_pins_exceptions import GitHubGraphQlClientError
import gh_profile_repo_pins.repo_pins_enum as enums
from typing import Any, Callable
from re import fullmatch


class GitHubApiProfiles:

    __GRAPH_QL_RATE_LIMIT_STR: str = queries.GRAPH_QL_RATE_LIMIT_STR

    def __init__(
        self,
        post_request: Callable[..., dict[str, Any]],
        author_obs: Callable[[dict[str, Any], str], dict[str, Any] | None],
        resolve_contributors: Callable[
            [list[dict[str, Any]], list[list[int]]], list[dict[str, Any]]
        ],
        dict_path: Callable[..., dict[str, Any]],
    ) -> None:
        self.__post_request: Callable[..., dict[str, Any]] = post_request
        self.__author_obs: Callable[[dict[str, Any], str], dict[str, Any] | None] = (
            author_obs
        )
        self.__resolve_contributors: Callable[
            [list[dict[str, Any]], list[list[int]]], list[dict[str, Any]]
        ] = resolve_contributors
        self.__dict_path: Callable[..., dict[str, Any]] = dict_path

    def get_contributor_profiles(
        self,
        repo_list: list[dict[str, Any]],
        timeout: float | int = 3.0,
        max_commits_per_repo: int = 24,
    ) -> list[dict[str, Any]]:
        for repo in repo_list:
            contributors: list[dict[str, Any]] = list(
                repo.get(enums.RepoPinsResDictKeys.LOCAL_CONTRIBUTORS.value, []) or []
            )
            if not contributors:
                continue

            unresolved: list[tuple[dict[str, Any], list[str]]] = []
            for contributor in contributors:
                _, _, emails = _local_id(data=contributor)
                is_gh_no_reply: bool = any(
                    fullmatch(
                        pattern=r"(?:(?:\d+)\+)?[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?@users\.noreply\.github\.com",
                        string=email,
                    )
                    for email in emails
                )
                if is_gh_no_reply:
                    continue
                raw_sha: list[Any] | Any = (
                    contributor.get(enums.RepoPinsResDictKeys.PROFILE_COMMITS.value, [])
                    or []
                )
                if not raw_sha:
                    fallback_sha: Any = contributor.get(
                        enums.RepoPinsResDictKeys.PROFILE_COMMIT.value, ""
                    )
                    raw_sha = [fallback_sha] if fallback_sha else []
                commit_sha: list[str] = [
                    str(sha).strip().lower()
                    for sha in raw_sha
                    if fullmatch(pattern=r"[0-9a-fA-F]{40}", string=str(sha).strip())
                ]
                if commit_sha:
                    unresolved.append((contributor, commit_sha))

            if not unresolved:
                continue

            url_tokens: list[str] = (
                str(repo.get(enums.RepoPinsResDictKeys.URL.value, "") or "")
                .rstrip("/")
                .split("/")
            )
            repo_name: str = str(
                repo.get(enums.RepoPinsResDictKeys.NAME.value, "") or ""
            ).strip()
            if len(url_tokens) < 2 or not repo_name:
                continue
            owner: str = url_tokens[-2].strip()

            selected_sha: list[str] = []
            seen_sha: set[str] = set()
            for _, unresolved_sha in unresolved:
                for sha in unresolved_sha:
                    if sha in seen_sha:
                        continue
                    seen_sha.add(sha)
                    selected_sha.append(sha)
                    if len(selected_sha) >= max_commits_per_repo:
                        break
                if len(selected_sha) >= max_commits_per_repo:
                    break
            if not selected_sha:
                continue

            fields: list[str] = []
            for idx, sha in enumerate[str](selected_sha):
                fields.append(f"""c{idx}: object(oid: "{sha}") {{
                      ... on Commit {{
                        committedDate
                        authors(first: 100) {{
                          nodes {{
                            name
                            email
                            user {{ login databaseId avatarUrl }}
                          }}
                        }}
                      }}
                    }}""")
            query: str = f"""query ($owner: String!, $name: String!) {{
              {self.__GRAPH_QL_RATE_LIMIT_STR}
              repository(owner: $owner, name: $name) {{
                {chr(10).join(fields)}
              }}
            }}"""

            try:
                res: dict[str, Any] = self.__post_request(
                    body_json={
                        "query": query,
                        "variables": {"owner": owner, "name": repo_name},
                    },
                    timeout=timeout,
                )
            except GitHubGraphQlClientError:
                continue

            repo_res: dict[str, Any] = self.__dict_path(
                res, enums.RepoPinsResDictKeys.DATA.value, "repository"
            )
            profile_obs: list[dict[str, Any]] = []
            for idx, _ in enumerate[str](selected_sha):
                commit: dict[Any, Any] | Any = repo_res.get(f"c{idx}") or {}
                commit_date: str = str(commit.get("committedDate", "") or "")
                for actor in (commit.get("authors") or {}).get("nodes", []) or []:
                    if not actor:
                        continue
                    obs: dict[str, Any] | None = self.__author_obs(actor, commit_date)
                    if obs is not None and (
                        obs.get(enums.RepoPinsResDictKeys.AVATAR_URL.value)
                        or obs.get(enums.RepoPinsResDictKeys.LOGIN.value)
                    ):
                        profile_obs.append(obs)

            if not profile_obs:
                continue

            repo[enums.RepoPinsResDictKeys.CONTRIBUTORS.value] = (
                self.__resolve_contributors(
                    profile_obs,
                    [[idx] for idx in range(len(profile_obs))],
                )
            )

        return repo_list
