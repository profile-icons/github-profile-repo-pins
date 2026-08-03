from logging import getLogger, Logger, StreamHandler, Formatter, INFO
from os import environ, getenv, path, listdir, unlink
import gh_profile_repo_pins.repo_pins_enum as enums
from json import load, loads, JSONDecodeError
from argparse import ArgumentParser
from re import sub, DOTALL
from shutil import rmtree
from pathlib import Path
from sys import stdout
from re import compile

SRC_REPO_NAME: str = "readme-repo-pins-src"
FILES_DIR: str = "files"
IMGS_DIR: str = "imgs"

USERNAME: str = environ.get("GH_USERNAME", "")
GH_API_TOKEN: str = environ.get(
    "GH_API_TOKEN", ""
)  # use default fine-grain PAT if local &/or for increased rate limit

REPO_OWNER: str = environ.get(
    "GH_REPO_OWNER", ""
)  # repo_owner is for repo code executed from/for, username is auth

# optional, can be a string (for all repos), or a dict (for individual repos) in the following format:
# EITHER (dict):
#
# {
#     <owner/repo>: theme_name (matching any key in themes.json),
# }
#
# OR (str):
#
# theme_name (matching any key in themes.json)
THEME: str = environ.get("THEME", "")

# optional, can be dict[dict] for individual pin imgs, or dict or single url/file path str if one img for all pins:
# EITHER (dict[dict]):
#
# {
#     <owner/repo>: (not required if one image is being used for all pins, otherwise required for individual pins):
#     {
#         img: url_or_path (required),
#         align: any val in enums.RepoPinsImgMediaBgImgAlign (optional),
#         mode: any val in enums.RepoPinsImgMediaBgImgMode (optional),
#         opacity: a float value between 0.0 and 1.0 (optional),
#     },
# }
#
# OR (dict):
#
# {
#     img: url_or_path (required),
#     align: any val in enums.RepoPinsImgMediaBgImgAlign (optional),
#     mode: any val in enums.RepoPinsImgMediaBgImgMode (optional),
#     opacity: a float value between 0.0 and 1.0 (optional),
# },
#
# OR (str):
#
# url_or_path (required, default options)
BG_IMG: str = environ.get("BG_IMG", "")

# optional, an exclusive list of repos separated by commas (owner/repo,owner/repo,...,owner/repo)
REPO_NAMES_EXCLUSIVE: str = environ.get("REPO_NAMES_EXCLUSIVE", "")

# optional configs, overrule REPO_NAMES_EXCLUSIVE if not null, otherwise overruled by REPO_NAMES_EXCLUSIVE (default)
NUM_REPO_PINS: str = environ.get("NUM_REPO_PINS", "")
REPO_PIN_ORDER: str = environ.get("REPO_PIN_ORDER", "")

# optional configs, overruled by REPO_NAMES_EXCLUSIVE
IS_EXCLUDE_REPOS_OWNED: str = environ.get("IS_EXCLUDE_REPOS_OWNED", "")
IS_EXCLUDE_REPOS_CONTRIBUTED: str = environ.get("IS_EXCLUDE_REPOS_CONTRIBUTED", "")

# optional config, independent to other configs, default False
IS_CONTRIBUTION_STATS: str = environ.get("IS_CONTRIBUTION_STATS", "")


def parse_bg_img(bg_img: str) -> dict | str | None:
    if bg_img:
        try:
            bg_img = loads(s=bg_img)
        except (JSONDecodeError, TypeError):
            if len(bg_img) == 0:
                bg_img = None
            elif (
                not isinstance(bg_img, str)
                or bg_img.startswith("{")
                or bg_img.startswith("}")
            ):
                raise AssertionError(
                    "The repo pin background img(s) url/filepath(s) must be correct dict/str format."
                )
    return bg_img


def parse_args() -> tuple:
    parser = ArgumentParser(
        description="GitHub API-fetch pinned/popular/contributed/select/etc repositories for a given username"
    )
    parser.add_argument(
        "--token", type=str, default=GH_API_TOKEN, help="A GitHub API token."
    )
    parser.add_argument(
        "--username",
        type=str,
        default=USERNAME if USERNAME else None,
        help="A GitHub account username.",
    )
    parser.add_argument(
        "--repos",
        type=str,
        default=(
            REPO_NAMES_EXCLUSIVE
            if REPO_NAMES_EXCLUSIVE and len(REPO_NAMES_EXCLUSIVE) > 0
            else None
        ),
        help=(
            "List of public repo names separated by commas in order of (pin) preference: 'owner/repo,owner/repo,...'. "
            "Overrules: --not_owned, --not_contributed, --pins (default), --order (default). "
            "Overruled by (when an arg is given): --pins, --order."
        ),
    )
    parser.add_argument(
        "--theme",
        type=str,
        default=THEME if THEME and len(THEME) > 0 else None,
        help=(
            "Repository pin image theme for all: 'theme'; or individual: {'repo': 'theme'}. Default: 'GitHub' theme."
        ),
    )
    parser.add_argument(
        "--img",
        type=str,
        default=BG_IMG if BG_IMG and len(BG_IMG) > 0 else None,
        help=(
            "Repository pin background image for all: dict | str; or individual: dict[dict]. Default: None."
        ),
    )
    parser.add_argument(
        "--pins",
        type=str,
        default=NUM_REPO_PINS if NUM_REPO_PINS else None,
        help="The maximum number of pinned repositories to fetch and display.",
    )
    parser.add_argument(
        "--order",
        type=str,
        choices=list(enums.RepositoryOrderFieldEnum.__members__.values()),
        default=(REPO_PIN_ORDER if REPO_PIN_ORDER else None),
        help="The order of repository data fetching from GitHub API and displaying of README pins where applicable.",
    )
    parser.add_argument(
        "--not-owned",
        action="store_true",
        default=True if IS_EXCLUDE_REPOS_OWNED else False,
        help="If owned repositories are excluded from complementing pins.",
    )
    parser.add_argument(
        "--not-contributed",
        action="store_true",
        default=True if IS_EXCLUDE_REPOS_CONTRIBUTED else False,
        help="If (not owned) repositories contributed to are excluded from complementing pins.",
    )
    parser.add_argument(
        "--owner",
        type=str,
        default=REPO_OWNER if REPO_OWNER else (USERNAME if USERNAME else None),
        help="The owner/org of repo code is executed from. To separate from authorisation (username) when required.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        default=True if IS_CONTRIBUTION_STATS else False,
        help="If repository contribution stats (commit add/del changes) are/not included. Default: False.",
    )
    args = parser.parse_args()

    exclusive_repo_name_pattern = compile(r"^\s*(?:,?\s*[\w.-]+/[\w.-]+\s*)*,?\s*$")
    assert (
        args.token is not None and isinstance(args.token, str) and len(args.token) > 0
    ), "A valid GitHub API token must be provided."
    assert args.username is None or (
        isinstance(args.username, str) and len(args.username) > 0
    ), "A valid GitHub account username must be provided."
    assert (
        args.repos is None
        or isinstance(args.repos, str)
        and exclusive_repo_name_pattern.match(args.repos)
    ), "The exclusive list of repo names (owner/repo,owner/repo,..) must be in a single string and separated by commas."
    assert (
        args.pins is None or int(args.pins) and int(args.pins) > 0
    ), "The maximum number of pinned repositories must be an int value and greater than 0."
    assert (
        args.order is None
        or isinstance(args.order, str)
        and args.order.lower()
        in [
            e.value.lower()
            for e in list(enums.RepositoryOrderFieldEnum.__members__.values())
        ]
    ), (
        f"The repository order of preference must match one of: "
        f"{list(enums.RepositoryOrderFieldEnum.__members__.values())}"
    )
    assert (
        args.owner is None or isinstance(args.owner, str) and len(args.owner) > 0
    ), "A valid GitHub repo owner must be provided and must match ownership of the repo code/workflow is executed from."

    if args.theme:
        try:
            args.theme = loads(s=args.theme)
        except (JSONDecodeError, TypeError):
            if not isinstance(args.theme, str):
                raise AssertionError(
                    "The repository theme must be either a string (for all repository pins) "
                    "or a dictionary (for individual repository pins)."
                )
            elif len(args.theme) == 0:
                args.theme = None

    return (
        args.token,
        args.username,
        args.repos,
        args.theme,
        parse_bg_img(bg_img=args.img),
        args.pins,
        args.order,
        args.not_owned,
        args.not_contributed,
        args.owner,
        args.stats,
    )


def tst_svg_parse_args() -> tuple:
    parser = ArgumentParser(description="Local test pin themes and SVG rendering.")
    parser.add_argument(
        "--theme",
        type=str,
        default="github_soft",
        help="A repo pin theme name, such as 'github', github_soft' or 'dracula', for examples.",
    )
    parser.add_argument(
        "--username",
        type=str,
        default="R055A",
        help="A GitHub account username.",
    )
    parser.add_argument(
        "--id",
        type=int,
        default=14985050,
        help="A GitHub account user database ID (used in the GitHub email).",
    )
    parser.add_argument(
        "--img",
        type=str,
        default=None,
        help="Repository pin background image: dict | str. Default: None.",
    )
    args = parser.parse_args()
    return (
        args.theme.lower() if args.theme else args.theme,
        args.username,
        args.id,
        parse_bg_img(bg_img=args.img),
    )


def get_logger() -> Logger:
    logger: Logger = getLogger(name=SRC_REPO_NAME)
    if not logger.handlers:
        stream_handler: StreamHandler = StreamHandler(stdout)
        stream_handler.setFormatter(
            fmt=Formatter(fmt="%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(hdlr=stream_handler)
        logger.setLevel(level=INFO)
    return logger


def set_git_creds(user_name: str, user_id: int | None) -> None:
    if getenv("GITHUB_ENV"):
        with open(file=getenv("GITHUB_ENV"), mode="a") as gh_env_file:
            gh_env_file.write(f"GH_USER_NAME={user_name}\n")
            gh_env_file.write(f"GH_USER_ID={user_id}\n")


def get_path(path_str: str = FILES_DIR) -> str:
    if not Path(path_str).exists():
        if Path(f"{SRC_REPO_NAME}/{path_str}").exists():
            return f"{SRC_REPO_NAME}/{path_str}"  # repo is cloned in workflow
        Path(path_str).mkdir()  # create dir if not exist (such as initial imgs/ dir)
    return path_str


def load_themes() -> dict[str, dict[str, dict[str, str]]]:
    with open(
        file=f"{get_path()}/themes.json", mode="r"
    ) as themes_file:  # correct for cloned repo
        return load(themes_file)


def load_img(img_path: str) -> bytes | str:
    with open(
        file=get_path(path_str=img_path), mode="rb"
    ) as img_file:  # fix for local repo
        return img_file.read()


def del_imgs() -> None:
    dir_name: str = get_path(path_str=IMGS_DIR)  # fix for local repo
    for filename in listdir(path=dir_name):
        file_path = path.join(dir_name, filename)
        if (
            filename.endswith(".svg")
            and path.isfile(path=file_path)
            or path.islink(path=file_path)
        ):
            unlink(path=file_path)
        elif path.isdir(s=file_path):
            rmtree(path=file_path)


def write_svg(svg_obj_str: str, file_name: str) -> None:
    with open(
        file=f"{get_path(path_str=IMGS_DIR)}/{file_name}.svg",
        mode="w",
        encoding="utf-8",  # fix for local repo
    ) as svg_file:
        svg_file.write(svg_obj_str)


def get_md_grid_pin_str(
    file_num: int, repo_name: str, repo_url: str, is_org: bool = False
) -> str:
    imgs_path: str = IMGS_DIR
    if is_org:
        imgs_path = f"../{imgs_path}"
    grid_str: str = ""
    if file_num % 2 == 0:
        grid_str += "\n"
    return (
        grid_str + f"[![{repo_name} pin img]({imgs_path}/{file_num}.svg)]({repo_url}) "
    )


def update_md_file(update_pin_display_str: str, is_org: bool = False) -> None:
    md_file_path: Path = Path("profile/README.md" if is_org else "README.md")
    if md_file_path.exists():
        update_data: str = sub(
            pattern=r"(<!-- START: REPO-PINS -->)(.*?)(<!-- END: REPO-PINS -->)",
            repl=rf"\1{update_pin_display_str}\n\3",
            string=md_file_path.read_text(encoding="utf-8"),
            flags=DOTALL,
        )
        md_file_path.write_text(data=update_data, encoding="utf-8")
    else:
        log: Logger = get_logger()
        log.warning(msg=f"File does not exist: {md_file_path.name}.")
