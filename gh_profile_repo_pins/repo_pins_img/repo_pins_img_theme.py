from gh_profile_repo_pins.repo_pins_exceptions import RepoPinImageThemeError
import gh_profile_repo_pins.repo_pins_enum as enums
from gh_profile_repo_pins.utils import load_themes
from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeSVG:
    canvas: str  # pin background
    border: str  # pin border
    text: str  # description text
    danger: str  # archive text/badge
    link: str  # hyperlink text (repo name)

    def __repr__(self) -> str:
        return f""":root {{
              --canvas: {self.canvas}; --border: {self.border}; 
              --text: {self.text}; --danger: {self.danger}; --link: {self.link};
            }}"""


class RepoPinImgTheme:

    def __init__(
        self,
        theme_name: enums.RepoPinsImgThemeName = enums.RepoPinsImgThemeName.GITHUB_SOFT,
    ) -> None:
        try:
            svg_themes_db: dict[
                enums.RepoPinsImgThemeName, dict[enums.RepoPinsImgThemeMode, ThemeSVG]
            ] = {
                enums.RepoPinsImgThemeName(k): {
                    enums.RepoPinsImgThemeMode(t): ThemeSVG(**d) for t, d in v.items()
                }
                for k, v in load_themes().items()
                if k in enums.RepoPinsImgThemeName
            }
            if not svg_themes_db:
                raise RepoPinImageThemeError(msg="No SVG themes are found.")
        except TypeError:
            raise RepoPinImageThemeError(
                msg=f"Theme '{theme_name.value}' is missing argument(s)."
            )

        if theme_name not in svg_themes_db:
            raise RepoPinImageThemeError(
                msg=f"Theme '{theme_name.value}' is not found in the database."
            )

        self.__svg_theme: dict[enums.RepoPinsImgThemeMode, ThemeSVG] | None = (
            svg_themes_db.get(
                enums.RepoPinsImgThemeName(theme_name),
                svg_themes_db.get(theme_name),
            )
        )
        if (
            not self.__svg_theme
            or enums.RepoPinsImgThemeMode.LIGHT not in self.__svg_theme
            or enums.RepoPinsImgThemeMode.DARK not in self.__svg_theme
        ):
            raise RepoPinImageThemeError(
                msg=f"Theme '{theme_name.value}' is missing dark/light mode(s)."
            )

    @property
    def svg_theme(self) -> dict[enums.RepoPinsImgThemeMode, ThemeSVG] | None:
        return self.__svg_theme
