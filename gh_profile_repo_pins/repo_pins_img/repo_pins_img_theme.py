from gh_profile_repo_pins.repo_pins_exceptions import RepoPinImageThemeError
import gh_profile_repo_pins.repo_pins_enum as enums
from utils.utils import load_themes
from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeSVG:
    canvas: str  # pin background
    border: str  # pin border
    text: str  # description text
    danger: str  # archive text/badge
    link: str  # hyperlink text (repo name)
    user_border: str | None = None  # highlighted user avatar border

    def __repr__(self) -> str:
        return f""":root {{
              --canvas: {self.canvas}; --border: {self.border}; 
              --text: {self.text}; --danger: {self.danger}; --link: {self.link};
              --user-border: {self.user_border or self.link};
            }}"""


ThemeMap = dict[enums.RepoPinsImgThemeMode, ThemeSVG]
ThemeDatabase = dict[enums.RepoPinsImgThemeName, ThemeMap]


class RepoPinImgTheme:

    def __init__(
        self,
        theme_name: enums.RepoPinsImgThemeName = enums.RepoPinsImgThemeName.GITHUB_SOFT,
    ) -> None:
        try:
            themes: ThemeDatabase = {
                enums.RepoPinsImgThemeName(name): {
                    enums.RepoPinsImgThemeMode(mode): ThemeSVG(**data)
                    for mode, data in theme.items()
                }
                for name, theme in load_themes().items()
                if name in enums.RepoPinsImgThemeName
            }
            if not themes:
                raise RepoPinImageThemeError(msg="No SVG themes are found.")
        except TypeError:
            raise RepoPinImageThemeError(
                msg=f"Theme '{theme_name.value}' is missing argument(s)."
            )

        if theme_name not in themes:
            raise RepoPinImageThemeError(
                msg=f"Theme '{theme_name.value}' is not found in the database."
            )

        self.__svg_theme = themes[theme_name]
        if not {
            enums.RepoPinsImgThemeMode.LIGHT,
            enums.RepoPinsImgThemeMode.DARK,
        }.issubset(self.__svg_theme):
            raise RepoPinImageThemeError(
                msg=f"Theme '{theme_name.value}' is missing dark/light mode(s)."
            )

    @property
    def svg_theme(self) -> ThemeMap:
        return self.__svg_theme
