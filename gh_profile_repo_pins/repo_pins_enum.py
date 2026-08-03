from sys import modules
from enum import Enum


class RepositoryOrderFieldEnum(Enum):
    STARGAZERS = "stargazerCount"
    NAME = "name"
    CREATED_AT = "createdAt"
    UPDATED_AT = "updatedAt"
    PUSHED_AT = "pushedAt"
    RANDOM = "random"


class RepoPinsImgMediaImgMime(Enum):
    PNG = "image/png"
    JPG = "image/jpeg"
    SVG = "image/svg+xml"
    GIF = "image/gif"
    WEB = "image/webp"


class RepoPinsImgMediaImgAlignX(Enum):
    xMin = "xmin"
    xMid = "xmid"
    xMax = "xmax"


class RepoPinsImgMediaImgAlignY(Enum):
    YMin = "ymin"
    YMid = "ymid"
    YMax = "ymax"


class RepoPinsImgMediaImgAlign(Enum):
    xMinYMin = (
        RepoPinsImgMediaImgAlignX.xMin.value + RepoPinsImgMediaImgAlignY.YMin.value
    )
    xMinYMid = (
        RepoPinsImgMediaImgAlignX.xMin.value + RepoPinsImgMediaImgAlignY.YMid.value
    )
    xMinYMax = (
        RepoPinsImgMediaImgAlignX.xMin.value + RepoPinsImgMediaImgAlignY.YMax.value
    )
    xMidYMin = (
        RepoPinsImgMediaImgAlignX.xMid.value + RepoPinsImgMediaImgAlignY.YMin.value
    )
    xMidYMid = (
        RepoPinsImgMediaImgAlignX.xMid.value + RepoPinsImgMediaImgAlignY.YMid.value
    )
    xMidYMax = (
        RepoPinsImgMediaImgAlignX.xMid.value + RepoPinsImgMediaImgAlignY.YMax.value
    )
    xMaxYMin = (
        RepoPinsImgMediaImgAlignX.xMax.value + RepoPinsImgMediaImgAlignY.YMin.value
    )
    xMaxYMid = (
        RepoPinsImgMediaImgAlignX.xMax.value + RepoPinsImgMediaImgAlignY.YMid.value
    )
    xMaxYMax = (
        RepoPinsImgMediaImgAlignX.xMax.value + RepoPinsImgMediaImgAlignY.YMax.value
    )


class RepoPinsImgMediaImgMode(Enum):
    SLICE = "cover"
    MEET = "contain"
    NONE = "stretch"


class RepoPinsImgThemeName(Enum):
    GITHUB = "github"
    GITHUB_SOFT = "github_soft"
    BG_IMG_CONTRAST = "bg_img_contrast"
    CATPPUCCIN = "catppuccin"
    DRACULA = "dracula"
    GRUVBOX = "gruvbox"
    NORD = "nord"
    ONE_DARK = "one_dark"
    SOLARIZED = "solarized"
    TOKYO_NIGHT = "tokyo_night"


class RepoPinsImgThemeMode(Enum):
    LIGHT = "light"
    DARK = "dark"


class RepoPinsResDictKeys(Enum):
    DATA = "data"
    ERROR = "error"
    MESSAGE = "message"
    RATE_LIMIT = "rateLimit"
    COST = "cost"
    URL = "url"
    URL_CUSTOM = "homepageUrl"
    USER = "user"
    VIEWER = "viewer"
    NAME = "name"
    OWNER = "owner"
    LOGIN = "login"
    PARENT = "parent"
    OWNER_REPO = "nameWithOwner"
    STARS = "stargazerCount"
    CONTRIBUTION = "contribution_data"
    STATS = "stats"
    FORK_COUNT = "forkCount"
    ISSUES = "issues"
    ISSUES_HELP = "issuesHelp"
    PULL_REQUESTS = "pullRequests"
    DESCRIPTION = "description"
    IS_FORK = "isFork"
    IS_TEMPLATE = "isTemplate"
    IS_ARCHIVE = "isArchived"
    IS_PRIVATE = "isPrivate"
    TTL_COUNT = "totalCount"
    LANGUAGE = "primaryLanguage"
    COLOR = "color"
    IMG = "img"
    CREATED_AT = "createdAt"
    DB_ID = "databaseId"
    EMAIL = "email"
    AUTHOR = "author"
    REPOSITORY_OWNER = "repositoryOwner"
    TYPENAME = "__typename"
    ORGANIZATION = "organization"


def update_enum(enum_cls: type[Enum], enum_dict: dict[str, str]) -> None:
    updated_enum: Enum = Enum(
        enum_cls.__name__,
        {**{m.name: m.value for m in enum_cls}, **enum_dict},
        type=str,
        module=enum_cls.__module__,
    )
    setattr(modules[enum_cls.__module__], enum_cls.__name__, updated_enum)
