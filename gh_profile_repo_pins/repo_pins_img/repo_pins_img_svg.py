from gh_profile_repo_pins.repo_pins_img.repo_pins_img_theme import (
    RepoPinImgTheme,
    ThemeSVG,
)
from gh_profile_repo_pins.repo_pins_img.repo_pins_img_data import (
    RepoPinContributor,
    RepoPinImgData,
)
from gh_profile_repo_pins.repo_pins_img.repo_pins_img_media import RepoPinImgMedia
from gh_profile_repo_pins.repo_pins_exceptions import RepoPinImageMediaError
import gh_profile_repo_pins.repo_pins_enum as enums
from collections.abc import Callable


class RepoPinImg:

    __SCALE: float | int = 0.937
    __WIDTH: float | int = round(440 * __SCALE)
    __HEIGHT: float | int = round(143 * __SCALE)
    __BASE_PADDING: int = 17
    __PADDING: float | int = round(__BASE_PADDING * __SCALE)
    __ROUNDING: float | int = round(6 * __SCALE)
    __NAME_SIZE: float | int = 14 * __SCALE
    __NAME_WEIGHT: int = 500
    __META_SIZE: float | int = 13 * __SCALE
    __DESC_SIZE: float | int = 13 * __SCALE
    __DESC_LINE_H: float | int = 1.35 * __DESC_SIZE

    __RTL_LOCALES: frozenset[str] = frozenset(
        {
            "ar",
            "ckb",
            "fa",
            "he",
            "ps",
            "sd",
            "ug",
            "ur",
            "yi",
        }
    )

    __ICON_GITHUB_MARK: str = (
        "M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 "
        "0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53 "
        ".63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 "
        "0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82A7.65 7.65 0 0 1 8 3.87c.68 0 1.36.09 2 .27 "
        "1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95 "
        ".29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8Z"
    )

    __ICON_REPO: str = (
        "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 "
        "0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 "
        "1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 "
        ".25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"
    )
    __ICON_REPO_TEMPLATE: str = (
        "M13.25 8a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-.75a.75.75 0 0 1 "
        "0-1.5h.75v-.25a.75.75 0 0 1 .75-.75ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 "
        "1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2ZM2.75 8a.75.75 0 0 1 "
        ".75.75v.268c.083-.012.166-.018.25-.018h.5a.75.75 0 0 1 0 1.5h-.5a.25.25 0 0 0-.25.25v.75c0 "
        ".28.114.532.3.714a.75.75 0 1 1-1.05 1.072A2.495 2.495 0 0 1 2 11.5V8.75A.75.75 0 0 1 2.75 8ZM11 .75a.75.75 0 "
        "0 1 .75-.75h1.5a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0V1.5h-.75A.75.75 0 0 1 11 .75Zm-5 0A.75.75 0 0 1 "
        "6.75 0h2.5a.75.75 0 0 1 0 1.5h-2.5A.75.75 0 0 1 6 .75Zm0 9A.75.75 0 0 1 6.75 9h2.5a.75.75 0 0 1 0 "
        "1.5h-2.5A.75.75 0 0 1 6 9.75ZM4.992.662a.75.75 0 0 1-.636.848c-.436.063-.783.41-.846.846a.751.751 0 0 "
        "1-1.485-.212A2.501 2.501 0 0 1 4.144.025a.75.75 0 0 1 .848.637ZM2.75 4a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 "
        "1-1.5 0v-1.5A.75.75 0 0 1 2.75 4Zm10.5 0a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0v-1.5a.75.75 0 0 1 .75-.75Z"
    )
    __ICON_REPO_PRIVATE_INNER: str = (
        "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0V1.5h-8a1 1 0 0 0-1 1v6.708A2.492 "
        "2.492 0 0 1 4.5 9h1.75a.75.75 0 0 1 0 1.5H4.5a1 1 0 1 0 0 2h1.75a.75.75 0 0 1 0 1.5H4.5A2.5 2.5 0 0 1 2 11.5v-9Z"
    )
    __ICON_REPO_PRIVATE_OUTER: str = (
        "M9 10.168V9a3 3 0 1 1 6 0v1.168c.591.281 1 .884 1 1.582v2.5A1.75 1.75 0 0 1 14.25 16h-4.5A1.75 1.75 0 0 1 8 "
        "14.25v-2.5c0-.698.409-1.3 1-1.582ZM13.5 10V9a1.5 1.5 0 0 0-3 0v1Z"
    )
    __ICON_REPO_ARCHIVE: str = (
        "M0 2.75C0 1.784.784 1 1.75 1h12.5c.966 0 1.75.784 1.75 1.75v1.5A1.75 1.75 0 0 1 14.25 6H1.75A1.75 1.75 0 0 1 "
        "0 4.25ZM1.75 7a.75.75 0 0 1 .75.75v5.5c0 .138.112.25.25.25h10.5a.25.25 0 0 0 .25-.25v-5.5a.75.75 0 0 1 1.5 "
        "0v5.5A1.75 1.75 0 0 1 13.25 15H2.75A1.75 1.75 0 0 1 1 13.25v-5.5A.75.75 0 0 1 1.75 7Zm0-4.5a.25.25 0 0 "
        "0-.25.25v1.5c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25v-1.5a.25.25 0 0 0-.25-.25ZM6.25 8h3.5a.75.75 0 0 "
        "1 0 1.5h-3.5a.75.75 0 0 1 0-1.5Z"
    )
    __ICON_STAR: str = (
        "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 "
        "4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 "
        "6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Zm0 2.445L6.615 5.5a.75.75 "
        "0 0 1-.564.41l-3.097.45 2.24 2.184a.75.75 0 0 1 .216.664l-.528 3.084 2.769-1.456a.75.75 0 0 1 "
        ".698 0l2.77 1.456-.53-3.084a.75.75 0 0 1 .216-.664l2.24-2.183-3.096-.45a.75.75 0 0 1-.564-.41L8 2.694Z"
    )
    __ICON_FORK: str = (
        "M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 2.25 0 1 1 1.5 0v.878a2.25 "
        "2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 0 1 1-1.5 0V8.5h-1.5A2.25 2.25 0 0 1 3.5 6.25v-.878a2.25 "
        "2.25 0 1 1 1.5 0ZM5 3.25a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Zm6.75.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 "
        "1.5Zm-3 8.75a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Z"
    )
    __ICON_ISSUE_INNER: str = "M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"
    __ICON_ISSUE_OUTER: str = (
        "M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z"
    )
    __ICON_PR: str = (
        "M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 "
        "3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 "
        "1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 "
        "0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z"
    )
    __ICON_COLLAB: str = (
        "M3.5 8a5.5 5.5 0 1 1 8.596 4.547 9.005 9.005 0 0 1 5.9 8.18.751.751 0 0 1-1.5.045 7.5 7.5 0 0 0-14.993 0 "
        ".75.75 0 0 1-1.499-.044 9.005 9.005 0 0 1 5.9-8.181A5.496 5.496 0 0 1 3.5 8ZM9 4a4 4 0 1 0 0 8 4 4 0 0 0 "
        "0-8Zm8.29 4c-.148 0-.292.01-.434.03a.75.75 0 1 1-.212-1.484 4.53 4.53 0 0 1 3.38 8.097 6.69 6.69 0 0 1 3.956 "
        "6.107.75.75 0 0 1-1.5 0 5.193 5.193 0 0 0-3.696-4.972l-.534-.16v-1.676l.41-.209A3.03 3.03 0 0 0 17.29 8Z"
    )
    __ICON_USER: str = (
        "M12 2.5a5.5 5.5 0 0 1 3.096 10.047 9.005 9.005 0 0 1 5.9 8.181.75.75 0 1 1-1.499.044 7.5 7.5 0 0 0-14.993 0 "
        ".75.75 0 0 1-1.5-.045 9.005 9.005 0 0 1 5.9-8.18A5.5 5.5 0 0 1 12 2.5ZM8 8a4 4 0 1 0 8 0 4 4 0 0 0-8 0Z"
    )

    __ICON_STATS: str = (
        "M1.75 1a.75.75 0 0 1 .75.75V13.5h11.75a.75.75 0 0 1 0 1.5H1.75A.75.75 0 0 1 1 14.25V1.75A.75.75 0 0 1 1.75 1Z "
        "M14.53 4.53a.75.75 0 0 0-1.06-1.06L9.25 7.69 7.03 5.47a.75.75 0 0 0-1.06 0L3.22 8.22a.75.75 0 1 0 1.06 "
        "1.06L6.5 7.06l2.22 2.22a.75.75 0 0 0 1.06 0l4.75-4.75Z"
    )

    __URL_PATH_STARS: str = "stargazers"
    __URL_PATH_FORKS: str = "forks"
    __URL_PATH_ISSUES: str = enums.RepoPinsResDictKeys.ISSUES.value.lower()
    __URL_PATH_PULLS: str = "pulls"
    __URL_PATH_CONTRIBUTORS: str = "graphs/contributors"

    __BADGE_PUBLIC: str = "Public"
    __BADGE_PRIVATE: str = "Private"
    __BADGE_ARCHIVE: str = " archive"
    __BADGE_TEMPLATE: str = " template"

    __MAX_STAT_NUMS: int = 1_000_000_000
    __MAX_CONTRIBUTOR_AVATARS: int = 4
    __USER_BORDER_STROKE_WIDTH: float | int = 2.25

    __UNKNOWN_AVATAR_BG: str = "#d0d7de"
    __UNKNOWN_AVATAR_FG: str = "#57606a"
    __UNKNOWN_AVATAR_BORDER: str = "#8c959f"

    __WIDE_CHARS: set[str] = set("mwMW@&%#$")
    __NARROW_CHARS: set[str] = set("il!|:;.,`'")

    def __init__(
        self,
        repo_pin_data: RepoPinImgData,
        is_translate: bool = False,
        is_nllb_trans: bool = False,
    ) -> None:
        self.__repo_pin_data: RepoPinImgData = repo_pin_data
        self.__repo_pin_theme: dict[enums.RepoPinsImgThemeMode, ThemeSVG] = (
            RepoPinImgTheme(
                theme_name=self.__repo_pin_data.theme,
            ).svg_theme
        )
        self.__repo_pin_translator = None
        if is_translate:
            from gh_profile_repo_pins.repo_pins_img.repo_pins_img_i18n import (
                RepoPinImgTranslator,
            )

            self.__repo_pin_translator = RepoPinImgTranslator()
        self.__is_nllb_trans: bool = is_nllb_trans
        self.__svg_str: str = ""

    @staticmethod
    def __format_svg_txt(txt: str) -> str:
        return (
            txt.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def __theme_style_block(self) -> str | AttributeError:
        css: str = """
          <style>
            svg {
              background: transparent;
            }
            """ + str(self.__repo_pin_theme.get(enums.RepoPinsImgThemeMode.LIGHT))
        css += """
            @media (prefers-color-scheme: dark) {
            """ + str(self.__repo_pin_theme.get(enums.RepoPinsImgThemeMode.DARK)) + "}"
        return css + ("""
            text { 
              font-family: -apple-system, 
              BlinkMacSystemFont, 
              "Segoe UI", 
              "Noto Sans", 
              Helvetica, 
              Arial, 
              sans-serif; 
            } 
          </style>""")

    def __char_width(self, char: str, font_px: float | int) -> float | int:
        factor: float | int = (
            0.68
            if char in self.__WIDE_CHARS
            else 0.28 if char in self.__NARROW_CHARS else 0.33 if char == " " else 0.53
        )
        return font_px * factor

    def __measure(self, txt: str, font_px: float | int) -> float | int:
        if not txt:
            return 0.0
        total: float | int = sum(self.__char_width(char, font_px) for char in txt)
        return max(
            0.0, total - min(total * 0.08, max(0, len(txt) - 1) * (0.02 * font_px))
        )

    def __truncate_to_width(self, txt: str, max_w: float | int) -> str:
        if self.__measure(txt=txt, font_px=self.__NAME_SIZE) <= max_w:
            return txt

        ell: str = "…"
        if self.__measure(txt=ell, font_px=self.__NAME_SIZE) > max_w:
            return ""

        start, end = 0, len(txt)
        while start < end:
            mid: int = (start + end + 1) // 2
            if self.__measure(txt=txt[:mid] + ell, font_px=self.__NAME_SIZE) <= max_w:
                start = mid
            else:
                end = mid - 1
        return (txt[:start] + ell) if start > 0 else ell

    def __href_link_open(self, url: str, url_path: str | None = None) -> None:
        self.__svg_str += (
            f'<a href="{url}/{url_path if url_path else ""}" target="_blank">'
        )

    def __href_link_close(self) -> None:
        self.__svg_str += "</a>"

    def __repo_name(
        self, header_y: float | int, name_badge_gap: float | int, badge_w: float | int
    ) -> None:
        name_x: float | int = self.__PADDING + round(18 * self.__SCALE)
        max_name_w: float | int = (
            (self.__WIDTH - self.__PADDING)
            - name_x
            - name_badge_gap
            - badge_w
            - max(4.0, 7.0 * self.__SCALE, 0.3 * self.__NAME_SIZE)
        )
        display_name: str = self.__truncate_to_width(
            txt=f"{self.__repo_pin_data.repo_name}",
            max_w=max_name_w if max_name_w > 0 else 0,
        )

        self.__href_link_open(url=self.__repo_pin_data.url)
        self.__svg_str += (
            f"<text "
            f'x="{name_x}" '
            f'y="{header_y}" '
            f'font-size="{self.__NAME_SIZE}" '
            f'fill="var(--link)"'
            f">"
        )
        owner_repo: list[str] = display_name.split(sep="/", maxsplit=1)
        if len(owner_repo) > 1:
            self.__svg_str += f'<tspan font-weight="500">{owner_repo[0]}/</tspan>'
        self.__svg_str += f'<tspan font-weight="700">{owner_repo[-1]}</tspan>'
        self.__svg_str += "</text>"
        self.__href_link_close()

    def __badge_layout(
        self, header_y: float | int
    ) -> tuple[float | int, float | int, float | int, float | int, float | int, str]:
        badge_txt: str = (
            self.__BADGE_PRIVATE
            if self.__repo_pin_data.is_private
            else self.__BADGE_PUBLIC
        ) + (
            self.__BADGE_ARCHIVE
            if self.__repo_pin_data.is_archived
            else (self.__BADGE_TEMPLATE if self.__repo_pin_data.is_template else "")
        )
        badge_font_size: float | int = self.__NAME_SIZE * 0.7
        badge_w: float | int = (
            int(round(self.__measure(txt=badge_txt, font_px=badge_font_size) + 0.5))
            + self.__PADDING
        )
        badge_h: float | int = round(badge_font_size + self.__ROUNDING * 1.1)
        badge_x: float | int = (self.__WIDTH - self.__PADDING) - badge_w
        badge_y: float | int = header_y - (badge_h * 0.8)
        return badge_x, badge_y, badge_h, badge_w, badge_font_size, badge_txt

    def __badge(
        self,
        badge_x: float | int,
        badge_y: float | int,
        badge_h: float | int,
        font_size: float | int,
        badge_w: float | int,
        badge_txt: str,
    ) -> str:
        return (
            f'<g transform="translate({badge_x:.2f},{badge_y:.2f})">'
            f'<rect width="{badge_w}" '
            f'height="{badge_h}" '
            f'rx="{round(badge_h / 2)}" '
            f'ry="{round(badge_h / 2)}" '
            f'fill="transparent" '
            f'stroke="{"var(--danger)" if self.__repo_pin_data.is_archived else "var(--border)"}"/>'
            f'<text x="{self.__PADDING / 2}" '
            f'y="{round(badge_h / 2 + font_size / 2) - 1}" '
            f'font-size="{font_size}" '
            f'fill="{"var(--danger)" if self.__repo_pin_data.is_archived else "var(--text)"}" '
            f'textLength="{badge_w - self.__PADDING}" '
            f'lengthAdjust="spacingAndGlyphs">'
            f"{self.__format_svg_txt(txt=badge_txt)}"
            f"</text>"
            f"</g>"
        )

    def __multi_lang_switch(
        self,
        input_txt: str,
        render: Callable[[str, str | None], str],
    ) -> str:
        if self.__repo_pin_translator is None:
            return render(input_txt, None)

        svg_parts: list[str] = ["<switch>"]
        for lang, translated_txt in self.__repo_pin_translator.translate_all(
            input_txt=input_txt,
            is_nllb_trans=self.__is_nllb_trans,
        ).items():
            svg_parts.extend(
                (
                    f'<g systemLanguage="{lang}">',
                    render(translated_txt, lang),
                    "</g>",
                )
            )
        svg_parts.extend(("<g>", render(input_txt, None), "</g></switch>"))
        return "".join(svg_parts)

    def __badge_multi_lang(
        self,
        badge_x: float | int,
        badge_y: float | int,
        badge_h: float | int,
        font_size: float | int,
        badge_w: float | int,
        badge_txt: str,
    ) -> str:
        return self.__multi_lang_switch(
            input_txt=badge_txt,
            render=lambda txt, _lang: self.__badge(
                badge_x=badge_x,
                badge_y=badge_y,
                badge_h=badge_h,
                font_size=font_size,
                badge_w=badge_w,
                badge_txt=txt,
            ),
        )

    def __header(self, header_y: float | int) -> None:
        badge_x, badge_y, badge_h, badge_w, badge_font_size, badge_txt = (
            self.__badge_layout(header_y=header_y)
        )

        name_badge_gap: float | int = round(self.__NAME_SIZE * 0.6)
        self.__repo_name(
            header_y=header_y, name_badge_gap=name_badge_gap, badge_w=badge_w
        )

        self.__svg_str += self.__badge_multi_lang(
            badge_x=badge_x,
            badge_y=badge_y,
            badge_h=badge_h,
            font_size=badge_font_size,
            badge_w=badge_w,
            badge_txt=badge_txt,
        )

    def __wrap_lines(
        self,
        description_txt: str,
        max_width_px: float | int,
        area_height_px: float | int,
    ) -> list[str]:
        if not description_txt or area_height_px - self.__DESC_SIZE < -1e-6:
            return []

        max_lines: int = max(
            0,
            min(
                3,
                1
                + max(
                    0,
                    int((area_height_px - self.__DESC_SIZE) // self.__DESC_LINE_H),
                ),
            ),
        )
        words: list[str] = description_txt.strip().split(" ")
        lines: list[str] = []
        cur_line: str = ""

        for word in words:
            next_line: str = f"{cur_line} {word}".strip() if cur_line else word
            if self.__measure(txt=next_line, font_px=self.__DESC_SIZE) <= max_width_px:
                cur_line = next_line
            elif cur_line:
                lines.append(cur_line)
                cur_line = word
            else:
                part_word: str = ""
                for char in word:
                    if (
                        self.__measure(txt=part_word + char, font_px=self.__DESC_SIZE)
                        > max_width_px
                    ):
                        break
                    part_word += char
                lines.append(part_word or word[:1])
                cur_line = word[len(part_word) :].lstrip()

            if len(lines) == max_lines:
                break

        if cur_line and len(lines) < max_lines:
            lines.append(cur_line)

        lines = lines[:max_lines]
        if not lines:
            return lines

        last_line: str = lines[-1]
        if self.__measure(
            txt=last_line, font_px=self.__DESC_SIZE
        ) > max_width_px or len(" ".join(lines)) < len(" ".join(words)):
            _ellipsis: str = "…"
            while (
                last_line
                and self.__measure(txt=last_line + _ellipsis, font_px=self.__DESC_SIZE)
                > max_width_px
            ):
                last_line = last_line[:-1]
            lines[-1] = last_line + _ellipsis if last_line else _ellipsis

        return lines

    def __parent_repo(self):
        pass  # TODO

    def __description(
        self,
        description_txt: str,
        description_y: float | int,
        description_h: float | int,
        is_rtl: bool = False,
    ) -> str:
        lines: list[str] = self.__wrap_lines(
            description_txt=description_txt,
            max_width_px=self.__WIDTH - self.__PADDING * 2,
            area_height_px=max(0.0, description_h),
        )
        return "".join(
            f"<text "
            f'x="{self.__WIDTH - self.__PADDING if is_rtl else self.__PADDING}" '
            f'y="{description_y + self.__DESC_SIZE + i * self.__DESC_LINE_H:.2f}" '
            f'font-size="{self.__DESC_SIZE}" '
            f'fill="var(--text)" '
            f"{(
                'direction="rtl" unicode-bidi="plaintext" text-anchor="start" '
                if is_rtl
                else ""
            )}>"
            f"{self.__format_svg_txt(line)}"
            f"</text>"
            for i, line in enumerate[str](lines)
        )

    def __description_multi_lang(
        self,
        description_txt: str,
        description_y: float | int,
        description_h: float | int,
    ) -> str:
        return self.__multi_lang_switch(
            input_txt=description_txt,
            render=lambda txt, lang: self.__description(
                description_txt=txt,
                description_y=description_y,
                description_h=description_h,
                is_rtl=bool(lang and lang in self.__RTL_LOCALES),
            ),
        )

    def __body(self, body_y: float | int, body_h: float | int) -> None:
        if self.__repo_pin_data.is_fork and self.__repo_pin_data.parent:
            self.__parent_repo()  # TODO
        if self.__repo_pin_data.description:
            self.__svg_str += self.__description_multi_lang(
                description_txt=self.__repo_pin_data.description,
                description_y=body_y,
                description_h=body_h,
            )

    def __render_icon(
        self, path_d: str, x: float | int, y: float | int, size: float | int
    ) -> str:
        return (
            f"<g "
            f'transform="translate({x:.2f},{y:.2f}) '
            f'scale({size / self.__BASE_PADDING:.4f})"'
            f">"
            f"<path "
            f'd="{path_d}" '
            f'fill="var(--text)" '
            f'stroke="none" '
            f'stroke-width="0" '
            f'fill-rule="evenodd"'
            f"/>"
            f"</g>"
        )

    def __fmt_footer_stats_str(self, stats_count: int) -> str:
        for div, mag in [(self.__MAX_STAT_NUMS, "B"), (1_000_000, "M"), (1_000, "K")]:
            if stats_count >= div:
                return f"{stats_count / div:.1f}".rstrip("0").rstrip(".") + mag
        return str(stats_count)

    def __footer_stats_width(self, stats_count: int) -> float | int:
        if stats_count <= 0:
            return 0
        txt = self.__fmt_footer_stats_str(stats_count=stats_count)
        txt_w = self.__measure(txt=txt, font_px=self.__META_SIZE)
        return max(self.__META_SIZE, self.__PADDING + txt_w)

    def __footer_stats(
        self,
        stats_icons: list[str],
        stats_count: int,
        footer_x: float | int,
        footer_y: float | int,
        footer_h: float | int,
        is_collab_icon: bool = False,
    ) -> float | int:
        if stats_count <= 0:
            return footer_x

        width: float | int = self.__footer_stats_width(stats_count=stats_count)
        self.__svg_str += (
            "<g>"
            f'<rect x="{footer_x:.2f}" '
            f'y="{footer_y - footer_h:.2f}" '
            f'width="{width:.2f}" '
            f'height="{footer_h:.2f}" '
            'fill="transparent" pointer-events="all" style="cursor:pointer;"/>'
            f"{"".join(
                self.__render_icon(
                    path_d=stats_icon,
                    x=footer_x,
                    y=footer_y - footer_h * 0.85,
                    size=self.__META_SIZE * (0.75 if is_collab_icon else 1),
                )
                for stats_icon in stats_icons
            )}"
            f'<text x="{footer_x + self.__PADDING:.2f}" '
            f'y="{footer_y:.2f}" font-size="{self.__META_SIZE}" '
            f'fill="var(--text)">{self.__fmt_footer_stats_str(stats_count=stats_count)}</text>'
            "</g>"
        )
        return footer_x + width

    def __footer_txt(
        self,
        txt: str,
        txt_x: float | int,
        footer_y: float | int,
        fill: str = "var(--text)",
    ) -> float | int:
        self.__svg_str += (
            f'<text x="{txt_x:.2f}" y="{footer_y:.2f}" '
            f'font-size="{self.__META_SIZE}" fill="{fill}">{txt}</text>'
        )
        return txt_x + self.__measure(txt=txt, font_px=self.__META_SIZE)

    def __footer_primary_language_width(self) -> float | int:
        txt_x = self.__ROUNDING * 3
        txt_w = self.__measure(
            txt=self.__repo_pin_data.primary_language_name, font_px=self.__META_SIZE
        )
        return max(self.__ROUNDING * 2, txt_x + txt_w)

    def __footer_primary_language(
        self, footer_x: float | int, footer_y: float | int, footer_h: float | int
    ) -> float | int:
        circle_cx = footer_x + self.__ROUNDING
        self.__svg_str += (
            f'<circle cx="{circle_cx:.2f}" '
            f'cy="{footer_y - (footer_h / 2) + 1.75:.2f}" '
            f'r="{self.__ROUNDING}" '
            f'fill="{self.__repo_pin_data.primary_language_color}"/>'
        )
        txt_x = footer_x + self.__ROUNDING * 3
        self.__footer_txt(
            txt=self.__repo_pin_data.primary_language_name,
            txt_x=txt_x,
            footer_y=footer_y,
        )
        return footer_x + self.__footer_primary_language_width()

    def __footer_stats_entry(
        self,
        footer_x: float | int,
        footer_y: float | int,
        footer_h: float | int,
        stats_url_path: str,
        stats_icon: str,
        stats_count: int,
    ) -> float | int:
        self.__href_link_open(
            url=self.__repo_pin_data.url,
            url_path=(stats_url_path if not self.__repo_pin_data.is_private else None),
        )
        footer_x = self.__footer_stats(
            stats_icons=[stats_icon],
            stats_count=stats_count,
            footer_x=footer_x,
            footer_y=footer_y,
            footer_h=footer_h,
        )
        self.__href_link_close()
        return footer_x

    def __footer_stargazers(
        self, footer_x: float | int, footer_y: float | int, footer_h: float | int
    ) -> float | int:
        return self.__footer_stats_entry(
            footer_x=footer_x,
            footer_y=footer_y,
            footer_h=footer_h,
            stats_url_path=self.__URL_PATH_STARS,
            stats_icon=self.__ICON_STAR,
            stats_count=self.__repo_pin_data.stargazer_count,
        )

    def __footer_forks(
        self, footer_x: float | int, footer_y: float | int, footer_h: float | int
    ) -> float | int:
        return self.__footer_stats_entry(
            footer_x=footer_x,
            footer_y=footer_y,
            footer_h=footer_h,
            stats_url_path=self.__URL_PATH_FORKS,
            stats_icon=self.__ICON_FORK,
            stats_count=self.__repo_pin_data.fork_count,
        )

    def __footer_issues_width(self) -> float | int:
        width: float | int = self.__footer_stats_width(
            stats_count=self.__repo_pin_data.issue_open_count
        )
        if self.__repo_pin_data.issue_help_count:
            help_count: str = self.__fmt_footer_stats_str(
                stats_count=self.__repo_pin_data.issue_help_count
            )
            help_txt: str = f"({help_count})"
            width += self.__META_SIZE * 0.25 + self.__measure(
                txt=help_txt, font_px=self.__META_SIZE
            )
        return width

    def __footer_issues(
        self, footer_x: float | int, footer_y: float | int, footer_h: float | int
    ) -> float | int:
        self.__href_link_open(
            url=self.__repo_pin_data.url,
            url_path=(
                self.__URL_PATH_ISSUES if not self.__repo_pin_data.is_private else None
            ),
        )
        group_x: float | int = footer_x
        footer_x = self.__footer_stats(
            stats_icons=[self.__ICON_ISSUE_INNER, self.__ICON_ISSUE_OUTER],
            stats_count=self.__repo_pin_data.issue_open_count,
            footer_x=footer_x,
            footer_y=footer_y,
            footer_h=footer_h,
        )
        if self.__repo_pin_data.issue_help_count:
            footer_x += self.__META_SIZE * 0.25
            help_count: str = self.__fmt_footer_stats_str(
                stats_count=self.__repo_pin_data.issue_help_count
            )
            footer_x = self.__footer_txt(
                txt=f"({help_count})",
                txt_x=footer_x,
                footer_y=footer_y,
                fill="var(--danger)",
            )
        self.__href_link_close()
        return max(footer_x, group_x + self.__footer_issues_width())

    def __footer_pull_requests(
        self, footer_x: float | int, footer_y: float | int, footer_h: float | int
    ) -> float | int:
        return self.__footer_stats_entry(
            footer_x=footer_x,
            footer_y=footer_y,
            footer_h=footer_h,
            stats_url_path=self.__URL_PATH_PULLS,
            stats_icon=self.__ICON_PR,
            stats_count=self.__repo_pin_data.pull_request_count,
        )

    def __contribution_img(
        self,
        img: RepoPinImgMedia,
        footer_x: float | int,
        footer_y: float | int,
        footer_h: float | int,
        clip_id: str,
        is_user: bool = False,
    ) -> float | int:
        img.load()
        img_radius: float | int = self.__contributor_avatar_size() / 2
        footer_center_y: float | int = footer_y - footer_h / 2
        clip_path_id: str = f"avatarClip-{clip_id}"
        border: str = ""
        if is_user or self.__repo_pin_data.contributor_count > 1:
            stroke_width: float | int = (
                self.__USER_BORDER_STROKE_WIDTH if is_user else 1.5
            )
            border = (
                f'<circle cx="{footer_x + img_radius:.2f}" '
                f'cy="{footer_center_y:.2f}" '
                f'r="{max(0, img_radius - stroke_width / 2):.2f}" '
                f'fill="none" stroke="{"var(--user-border)" if is_user else "var(--canvas)"}" stroke-width="{stroke_width:.2f}"/>'
            )
        self.__svg_str += (
            "<defs>"
            f'<clipPath id="{clip_path_id}">'
            f'<circle cx="{footer_x + img_radius:.2f}" '
            f'cy="{footer_center_y:.2f}" r="{img_radius:.2f}" />'
            "</clipPath>"
            "</defs>"
            "<image "
            f'href="{img.encoded_url}" '
            f'x="{footer_x:.2f}" '
            f'y="{footer_center_y - img_radius:.2f}" '
            f'width="{self.__contributor_avatar_size():.2f}" '
            f'height="{self.__contributor_avatar_size():.2f}" '
            f'preserveAspectRatio="{img.mode.name.lower()}" '
            f'opacity="{img.opacity}" '
            f'clip-path="url(#{clip_path_id})" '
            "/>"
            f"{border}"
        )
        return footer_x + self.__contributor_avatar_size()

    def __unknown_contribution_img(
        self,
        footer_x: float | int,
        footer_y: float | int,
        footer_h: float | int,
        clip_id: str,
    ) -> float | int:
        img_radius: float | int = self.__contributor_avatar_size() / 2
        footer_center_y: float | int = footer_y - footer_h / 2
        clip_path_id: str = f"avatarClip-{clip_id}"
        stroke_width: float | int = 1.5
        q_mark_size: float | int = self.__contributor_avatar_size() * 0.72
        self.__svg_str += (
            "<defs>"
            f'<clipPath id="{clip_path_id}">'
            f'<circle cx="{footer_x + img_radius:.2f}" '
            f'cy="{footer_center_y:.2f}" r="{img_radius:.2f}" />'
            "</clipPath>"
            "</defs>"
            f'<g clip-path="url(#{clip_path_id})">'
            f'<circle cx="{footer_x + img_radius:.2f}" '
            f'cy="{footer_center_y:.2f}" r="{img_radius:.2f}" '
            f'fill="{self.__UNKNOWN_AVATAR_BG}" />'
            f'<path d="{self.__ICON_GITHUB_MARK}" '
            f'transform="translate({footer_x:.2f} {footer_center_y - img_radius:.2f}) '
            f'scale({self.__contributor_avatar_size() / 16:.5f})" fill="{self.__UNKNOWN_AVATAR_FG}" opacity="0.12" />'
            f'<text x="{footer_x + img_radius:.2f}" y="{footer_center_y + q_mark_size * 0.34:.2f}" '
            f'text-anchor="middle" fill="{self.__UNKNOWN_AVATAR_FG}" opacity="0.88" '
            f'font-size="{q_mark_size:.2f}px" font-weight="700">?</text>'
            "</g>"
            f'<circle cx="{footer_x + img_radius:.2f}" '
            f'cy="{footer_center_y:.2f}" '
            f'r="{max(0, img_radius - stroke_width / 2):.2f}" '
            f'fill="none" stroke="{self.__UNKNOWN_AVATAR_BORDER}" stroke-width="{stroke_width:.2f}"/>'
        )
        return footer_x + self.__contributor_avatar_size()

    def __footer_inline_txt(
        self, txt: str, txt_x: float | int, footer_y: float | int
    ) -> float | int:
        return self.__footer_txt(txt=txt, txt_x=txt_x, footer_y=footer_y)

    def __contributor_avatar_step(self) -> float | int:
        return self.__contributor_avatar_size() - self.__contributor_avatar_overlap()

    def __contributor_marker_gap(self) -> float | int:
        return self.__META_SIZE * 0.05

    def __render_contributor(
        self,
        contributor: RepoPinContributor | None,
        footer_x: float | int,
        footer_y: float | int,
        footer_h: float | int,
        clip_id: str,
        fallback_to_user: bool = False,
    ) -> None:
        if contributor is not None and (
            contributor.is_unknown or contributor.img is None
        ):
            self.__unknown_contribution_img(
                footer_x=footer_x,
                footer_y=footer_y,
                footer_h=footer_h,
                clip_id=f"{clip_id}-unknown",
            )
            return

        if contributor is None and not fallback_to_user:
            return

        try:
            self.__contribution_img(
                img=(
                    contributor.img
                    if contributor is not None and contributor.img is not None
                    else self.__repo_pin_data.user_img
                ),
                footer_x=footer_x,
                footer_y=footer_y,
                footer_h=footer_h,
                clip_id=clip_id,
                is_user=(
                    contributor.is_user
                    if contributor is not None
                    else self.__repo_pin_data.contributor_count == 1
                ),
            )
        except RepoPinImageMediaError:
            self.__unknown_contribution_img(
                footer_x=footer_x,
                footer_y=footer_y,
                footer_h=footer_h,
                clip_id=f"{clip_id}-unavailable",
            )

    def __contributor_avatar_size(self) -> float | int:
        return self.__META_SIZE * 2

    def __contributor_avatar_overlap(self) -> float | int:
        return self.__contributor_avatar_size() * 0.35

    def __contributor_avatar_count(self) -> int:
        if self.__repo_pin_data.contributor_count <= 0:
            return 0
        if self.__repo_pin_data.top_contributors:
            return min(
                self.__MAX_CONTRIBUTOR_AVATARS,
                len(self.__repo_pin_data.top_contributors),
            )
        return 1 if self.__repo_pin_data.contributor_count == 1 else 0

    def __user_outside_top_contributors(self) -> bool:
        user_idx: int | None = getattr(
            self.__repo_pin_data, "user_top_contributor_idx", None
        )
        return user_idx is not None and user_idx >= self.__MAX_CONTRIBUTOR_AVATARS

    def __contributor_overflow_marker_width(self) -> float | int:
        return self.__measure(txt="..", font_px=self.__META_SIZE)

    def __contributor_avatar_stack_width(self) -> float | int:
        avatar_count = self.__contributor_avatar_count()
        if not avatar_count:
            return 0

        avatar_size: float | int = self.__contributor_avatar_size()
        marker_gap: float | int = self.__contributor_marker_gap()
        marker_width: float | int = self.__contributor_overflow_marker_width()

        if self.__user_outside_top_contributors():
            leading_count: int = min(self.__MAX_CONTRIBUTOR_AVATARS - 1, avatar_count)
            width: float | int = (
                (
                    avatar_size + (leading_count - 1) * self.__contributor_avatar_step()
                    if leading_count
                    else 0
                )
                + marker_gap * 2
                + marker_width
                + avatar_size
            )
        else:
            width = avatar_size + (avatar_count - 1) * self.__contributor_avatar_step()

        if self.__show_trailing_contributor_overflow_marker():
            width += marker_gap + marker_width
        return width

    def __has_unknown_contributor_avatar(self) -> bool:
        return any(
            contributor.is_unknown
            for contributor in self.__repo_pin_data.top_contributors
        )

    def __show_trailing_contributor_overflow_marker(self) -> bool:
        if self.__user_outside_top_contributors():
            user_idx: int | None = self.__repo_pin_data.user_top_contributor_idx
            return bool(
                user_idx is not None
                and user_idx < self.__repo_pin_data.contributor_count - 1
            )
        if (
            self.__repo_pin_data.contributor_count == 1
            and not self.__repo_pin_data.top_contributors
        ):
            return False
        return self.__repo_pin_data.contributor_count > len(
            self.__repo_pin_data.top_contributors
        )

    def __is_contributor_count_visible(self) -> bool:
        return (
            self.__repo_pin_data.contributor_count > self.__MAX_CONTRIBUTOR_AVATARS
            or (
                self.__has_unknown_contributor_avatar()
                and self.__repo_pin_data.contributor_count
                > len(self.__repo_pin_data.top_contributors)
            )
        )

    def __footer_contributors_width(self) -> float | int:
        if self.__repo_pin_data.contributor_count <= 0:
            return 0

        content_x: float | int = self.__PADDING
        if self.__is_contributor_count_visible():
            content_x += self.__measure(
                txt=self.__fmt_footer_stats_str(
                    stats_count=self.__repo_pin_data.contributor_count
                ),
                font_px=self.__META_SIZE,
            )
            if self.__contributor_avatar_count():
                content_x += self.__META_SIZE * 0.3

        return max(
            self.__META_SIZE, content_x + self.__contributor_avatar_stack_width()
        )

    def __footer_contributors(
        self, footer_x: float | int, footer_y: float | int, footer_h: float | int
    ) -> float | int:
        if self.__repo_pin_data.contributor_count <= 0:
            return footer_x

        self.__href_link_open(
            url=self.__repo_pin_data.url,
            url_path=(
                self.__URL_PATH_CONTRIBUTORS
                if not self.__repo_pin_data.is_private
                else None
            ),
        )
        self.__svg_str += self.__render_icon(
            path_d=(
                self.__ICON_USER
                if self.__repo_pin_data.contributor_count == 1
                else self.__ICON_COLLAB
            ),
            x=footer_x,
            y=footer_y - footer_h * 0.85,
            size=self.__META_SIZE * 0.75,
        )

        content_x: float | int = footer_x + self.__PADDING
        if self.__is_contributor_count_visible():
            content_x = self.__footer_inline_txt(
                txt=self.__fmt_footer_stats_str(self.__repo_pin_data.contributor_count),
                txt_x=content_x,
                footer_y=footer_y,
            )
            if self.__contributor_avatar_count():
                content_x += self.__META_SIZE * 0.3

        contributors: list[RepoPinContributor | None] = list(
            self.__repo_pin_data.top_contributors[: self.__MAX_CONTRIBUTOR_AVATARS]
        )
        if not contributors and self.__repo_pin_data.contributor_count == 1:
            contributors = [None]

        marker_gap: float | int = self.__contributor_marker_gap()
        avatar_size: float | int = self.__contributor_avatar_size()
        avatar_step: float | int = self.__contributor_avatar_step()

        if self.__user_outside_top_contributors():
            leading: list[RepoPinContributor | None] = contributors[
                : self.__MAX_CONTRIBUTOR_AVATARS - 1
            ]
            for i, contributor in enumerate[RepoPinContributor | None](leading):
                self.__render_contributor(
                    contributor=contributor,
                    footer_x=content_x + i * avatar_step,
                    footer_y=footer_y,
                    footer_h=footer_h,
                    clip_id=f"contributor-{i}",
                )

            user_x: float | int = (
                self.__footer_inline_txt(
                    txt="..",
                    txt_x=(
                        content_x + (len(leading) - 1) * avatar_step + avatar_size
                        if leading
                        else content_x
                    )
                    + marker_gap,
                    footer_y=footer_y,
                )
                + marker_gap
            )
            self.__contribution_img(
                img=self.__repo_pin_data.user_img,
                footer_x=user_x,
                footer_y=footer_y,
                footer_h=footer_h,
                clip_id="contributor-user",
                is_user=True,
            )
            if self.__show_trailing_contributor_overflow_marker():
                self.__footer_inline_txt(
                    txt="..",
                    txt_x=user_x + avatar_size + marker_gap,
                    footer_y=footer_y,
                )
        else:
            for i, contributor in enumerate[RepoPinContributor | None](contributors):
                self.__render_contributor(
                    contributor=contributor,
                    footer_x=content_x + i * avatar_step,
                    footer_y=footer_y,
                    footer_h=footer_h,
                    clip_id=f"contributor-{i}",
                    fallback_to_user=True,
                )

            if self.__show_trailing_contributor_overflow_marker() and contributors:
                self.__footer_inline_txt(
                    txt="..",
                    txt_x=(
                        content_x
                        + (len(contributors) - 1) * avatar_step
                        + avatar_size
                        + marker_gap
                    ),
                    footer_y=footer_y,
                )

        self.__href_link_close()
        return footer_x + self.__footer_contributors_width()

    def __contribution_percentage_text(self) -> str:
        return f"{str(round(self.__repo_pin_data.contribution_perc, 1)).rstrip("0").rstrip(".")}%"

    def __footer_contribution_stats_width(self) -> float | int:
        if (
            not self.__repo_pin_data.contribution_perc
            or self.__repo_pin_data.contributor_count <= 1
        ):
            return 0
        return (
            self.__PADDING
            + self.__measure(
                txt=self.__contribution_percentage_text(), font_px=self.__META_SIZE
            )
            + self.__META_SIZE * 0.3
            + self.__contributor_avatar_size()
        )

    def __footer_contribution_stats(
        self, footer_x: float | int, footer_y: float | int, footer_h: float | int
    ) -> float | int:
        if self.__footer_contribution_stats_width() <= 0:
            return footer_x

        self.__href_link_open(
            url=self.__repo_pin_data.url,
            url_path=(
                self.__URL_PATH_CONTRIBUTORS
                if not self.__repo_pin_data.is_private
                else None
            ),
        )
        self.__svg_str += self.__render_icon(
            path_d=self.__ICON_STATS,
            x=footer_x,
            y=footer_y - footer_h * 0.85,
            size=self.__META_SIZE,
        )
        self.__contribution_img(
            img=self.__repo_pin_data.user_img,
            footer_x=self.__footer_inline_txt(
                txt=self.__contribution_percentage_text(),
                txt_x=footer_x + self.__PADDING,
                footer_y=footer_y,
            )
            + self.__META_SIZE * 0.3,
            footer_y=footer_y,
            footer_h=footer_h,
            clip_id="contribution-stats-user",
            is_user=True,
        )
        self.__href_link_close()
        return footer_x + self.__footer_contribution_stats_width()

    def __footer_group_gap(self, widths: list[float | int]) -> float | int:
        visible_widths: list[float | int] = [width for width in widths if width > 0]
        if len(visible_widths) <= 1:
            return 0
        return max(
            0.0,
            min(
                self.__META_SIZE,
                ((self.__WIDTH - self.__PADDING * 2) - sum(visible_widths))
                / (len(visible_widths) - 1),
            ),
        )

    def __footer(self, footer_y: float | int, footer_h: float | int) -> None:
        groups: list[tuple[float | int, Callable[..., float | int]]] = []

        def add_group(
            is_visible: bool,
            width: float | int,
            renderer: Callable[..., float | int],
        ) -> None:
            if is_visible:
                groups.append((width, renderer))

        add_group(
            is_visible=bool(self.__repo_pin_data.primary_language_name),
            width=self.__footer_primary_language_width(),
            renderer=self.__footer_primary_language,
        )
        add_group(
            is_visible=self.__repo_pin_data.stargazer_count > 0,
            width=self.__footer_stats_width(
                stats_count=self.__repo_pin_data.stargazer_count
            ),
            renderer=self.__footer_stargazers,
        )
        add_group(
            is_visible=self.__repo_pin_data.fork_count > 0,
            width=self.__footer_stats_width(
                stats_count=self.__repo_pin_data.fork_count
            ),
            renderer=self.__footer_forks,
        )
        add_group(
            is_visible=self.__repo_pin_data.issue_open_count > 0
            or self.__repo_pin_data.issue_help_count > 0,
            width=self.__footer_issues_width(),
            renderer=self.__footer_issues,
        )
        add_group(
            is_visible=self.__repo_pin_data.pull_request_count > 0,
            width=self.__footer_stats_width(
                stats_count=self.__repo_pin_data.pull_request_count
            ),
            renderer=self.__footer_pull_requests,
        )
        add_group(
            is_visible=self.__repo_pin_data.contributor_count > 0,
            width=self.__footer_contributors_width(),
            renderer=self.__footer_contributors,
        )
        contribution_width: float | int = self.__footer_contribution_stats_width()
        add_group(
            is_visible=contribution_width > 0,
            width=contribution_width,
            renderer=self.__footer_contribution_stats,
        )

        footer_x: float | int = self.__PADDING
        for i, (_, render_group) in enumerate(groups):
            footer_x = render_group(
                footer_x=footer_x,
                footer_y=footer_y,
                footer_h=footer_h,
            )
            if i < len(groups) - 1:
                footer_x += self.__footer_group_gap(
                    widths=[width for width, _ in groups]
                )

    def __bg_img(self) -> None:
        bg_img: RepoPinImgMedia | None = self.__repo_pin_data.bg_img
        if bg_img is None:
            return
        bg_img.load()
        self.__svg_str += (
            "<image "
            f'href="{bg_img.encoded_url}" '
            'x="0" '
            'y="0" '
            f'width="{self.__WIDTH}" '
            f'height="{self.__HEIGHT}" '
            f'preserveAspectRatio="{(
                bg_img.align.name + " "
                if bg_img.mode != enums.RepoPinsImgMediaImgMode.NONE
                else ""
            )}{bg_img.mode.name.lower()}" '
            f'opacity="{bg_img.opacity}" '
            "/>"
        )

    def __render_svg(self) -> None:
        header_y: float | int = self.__PADDING + self.__NAME_SIZE
        body_y: float | int = header_y + self.__PADDING
        body_h: float | int = max(0.0, self.__HEIGHT - self.__PADDING - body_y)
        footer_y: float | int = max(0.0, self.__HEIGHT - self.__PADDING)
        footer_h: float | int = self.__META_SIZE

        repo_icon: list[str] = (
            [self.__ICON_REPO_PRIVATE_INNER, self.__ICON_REPO_PRIVATE_OUTER]
            if self.__repo_pin_data.is_private
            else [
                (
                    self.__ICON_REPO_ARCHIVE
                    if self.__repo_pin_data.is_archived
                    else (
                        self.__ICON_REPO_TEMPLATE
                        if self.__repo_pin_data.is_template
                        else self.__ICON_REPO
                    )
                )
            ]
        )

        self.__svg_str = f"""<?xml version="1.0" encoding="UTF-8"?>
        <svg 
          width="{self.__WIDTH}" 
          height="{self.__HEIGHT}" 
          viewBox="0 0 {self.__WIDTH} {self.__HEIGHT}" 
          xmlns="http://www.w3.org/2000/svg" 
          role="img" 
          aria-label="{self.__repo_pin_data.repo_name}"
        >
          <title>{self.__repo_pin_data.repo_name}</title>
          {self.__theme_style_block()}
          <defs><clipPath id="clip"><rect 
            x="0" 
            y="0" 
            width="{self.__WIDTH}" 
            height="{self.__HEIGHT}" 
            rx="{self.__ROUNDING}" 
            ry="{self.__ROUNDING}"
          /></clipPath></defs>
          <g clip-path="url(#clip)">
            <rect 
              x="0" 
              y="0" 
              width="{self.__WIDTH}" 
              height="{self.__HEIGHT}" 
              fill="var(--canvas)" 
              stroke="var(--border)"
            />
            {"".join(
                [
                    self.__render_icon(
                        path_d=icon, 
                        x=self.__PADDING, 
                        y=header_y - (self.__NAME_SIZE * 0.85),
                        size=self.__PADDING,
                    )
                    for icon in repo_icon
                ]
            )}
        """
        if self.__repo_pin_data.bg_img:
            self.__bg_img()
        self.__header(header_y=header_y)
        self.__body(body_y=body_y, body_h=body_h)
        self.__footer(footer_y=footer_y, footer_h=footer_h)

        self.__svg_str += f"""
          </g>
          <rect 
            x="0.5" 
            y="0.5" 
            width="{self.__WIDTH - 1}" 
            height="{self.__HEIGHT - 1}" 
            rx="{self.__ROUNDING}" 
            ry="{self.__ROUNDING}" 
            fill="none" 
            stroke="var(--border)"
          />
        </svg>
        """

    @property
    def data(self) -> RepoPinImgData:
        return self.__repo_pin_data

    @property
    def svg(self) -> str:
        return self.__svg_str

    def render(self) -> None:
        self.__render_svg()


def tst_svg_render(
    test_theme_name: str = "github_soft",
    test_username: str = "R055A",
    test_user_id: int = 14985050,
    test_bg_img: dict | str | None = None,
) -> None:
    from gh_profile_repo_pins.repo_pins_exceptions import (
        RepoPinImageThemeError,
        RepoPinImageMediaError,
    )
    from gh_profile_repo_pins.repo_pins_generate import GenerateRepoPins
    from utils.utils import Logger, get_logger
    from utils.utils import write_svg

    log: Logger = get_logger()
    is_nllb_trans: bool = True

    GenerateRepoPins.update_themes()  # update the database with any new JSON themes not in enums.RepoPinsImgThemeName

    tst_input = [
        {
            enums.RepoPinsResDictKeys.NAME.value: "readme-repo-pins",
            enums.RepoPinsResDictKeys.STARS.value: 110_000,
            enums.RepoPinsResDictKeys.FORK_COUNT.value: 9_900_000_000,
            enums.RepoPinsResDictKeys.ISSUES.value: {
                enums.RepoPinsResDictKeys.TTL_COUNT.value: 10
            },
            enums.RepoPinsResDictKeys.ISSUES_HELP.value: {
                enums.RepoPinsResDictKeys.TTL_COUNT.value: 1
            },
            enums.RepoPinsResDictKeys.PULL_REQUESTS.value: {
                enums.RepoPinsResDictKeys.TTL_COUNT.value: 22
            },
            enums.RepoPinsResDictKeys.OWNER.value: {
                enums.RepoPinsResDictKeys.LOGIN.value: "profile-icons"
            },
            enums.RepoPinsResDictKeys.DESCRIPTION.value: "Lorem ipsum dolor sit amet, consectetur adipiscing elit, "
            "sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
            "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris "
            "nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in "
            "reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla "
            "pariatur. Excepteur sint occaecat cupidatat non proident, sunt in "
            "culpa qui officia deserunt mollit anim id est laborum.",
            enums.RepoPinsResDictKeys.URL.value: "https://github.com/profile-icons/readme-repo-pins",
            enums.RepoPinsResDictKeys.URL_CUSTOM.value: "https://github.com/FALSE/FALSE",
            enums.RepoPinsResDictKeys.LANGUAGE.value: {
                enums.RepoPinsResDictKeys.NAME.value: "MATLAB",
                enums.RepoPinsResDictKeys.COLOR.value: "#e16737",
            },
            enums.RepoPinsResDictKeys.IS_FORK.value: True,
            enums.RepoPinsResDictKeys.PARENT.value: {
                enums.RepoPinsResDictKeys.OWNER_REPO.value: "R055A/readme-repo-pins"
            },
            enums.RepoPinsResDictKeys.IS_TEMPLATE.value: True,
            enums.RepoPinsResDictKeys.IS_ARCHIVE.value: True,
            enums.RepoPinsResDictKeys.IS_PRIVATE.value: False,
            enums.RepoPinsResDictKeys.CONTRIBUTION.value: [
                {
                    enums.RepoPinsResDictKeys.LOGIN.value: test_username,
                    enums.RepoPinsResDictKeys.STATS.value: 737,
                    enums.RepoPinsResDictKeys.AUTHOR.value: [test_username],
                },
                {
                    enums.RepoPinsResDictKeys.LOGIN.value: "ANON1",
                    enums.RepoPinsResDictKeys.STATS.value: 100,
                    enums.RepoPinsResDictKeys.AUTHOR.value: ["ANON1"],
                },
                {
                    enums.RepoPinsResDictKeys.LOGIN.value: "ANON2",
                    enums.RepoPinsResDictKeys.STATS.value: 63,
                    enums.RepoPinsResDictKeys.AUTHOR.value: ["ANON2"],
                },
                {
                    enums.RepoPinsResDictKeys.LOGIN.value: "ANON3",
                    enums.RepoPinsResDictKeys.STATS.value: 100,
                    enums.RepoPinsResDictKeys.AUTHOR.value: ["ANON3"],
                },
            ],
        },
        {
            enums.RepoPinsResDictKeys.NAME.value: test_username,
            enums.RepoPinsResDictKeys.STARS.value: 0,
            enums.RepoPinsResDictKeys.FORK_COUNT.value: 1,
            enums.RepoPinsResDictKeys.ISSUES.value: {
                enums.RepoPinsResDictKeys.TTL_COUNT.value: 1
            },
            enums.RepoPinsResDictKeys.ISSUES_HELP.value: {
                enums.RepoPinsResDictKeys.TTL_COUNT.value: 0
            },
            enums.RepoPinsResDictKeys.PULL_REQUESTS.value: {
                enums.RepoPinsResDictKeys.TTL_COUNT.value: 1
            },
            enums.RepoPinsResDictKeys.OWNER.value: {
                enums.RepoPinsResDictKeys.LOGIN.value: test_username
            },
            enums.RepoPinsResDictKeys.DESCRIPTION.value: "Lorem ipsum dolor sit amet, consectetur adipiscing elit, "
            "sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
            enums.RepoPinsResDictKeys.URL.value: "https://github.com/FALSE/FALSE",
            enums.RepoPinsResDictKeys.URL_CUSTOM.value: f"https://github.com/{test_username}/{test_username}",
            enums.RepoPinsResDictKeys.LANGUAGE.value: {
                enums.RepoPinsResDictKeys.NAME.value: "Python",
                enums.RepoPinsResDictKeys.COLOR.value: "#3572A5",
            },
            enums.RepoPinsResDictKeys.IS_FORK.value: False,
            enums.RepoPinsResDictKeys.PARENT.value: {},
            enums.RepoPinsResDictKeys.IS_TEMPLATE.value: True,
            enums.RepoPinsResDictKeys.IS_ARCHIVE.value: False,
            enums.RepoPinsResDictKeys.IS_PRIVATE.value: True,
            enums.RepoPinsResDictKeys.CONTRIBUTION.value: [
                {enums.RepoPinsResDictKeys.LOGIN.value: test_username},
            ],
        },
        {
            enums.RepoPinsResDictKeys.NAME.value: "readme-repo-pins-readme-repo-pins-badge-repo-pins",
            enums.RepoPinsResDictKeys.STARS.value: 0,
            enums.RepoPinsResDictKeys.FORK_COUNT.value: 0,
            enums.RepoPinsResDictKeys.ISSUES.value: {
                enums.RepoPinsResDictKeys.TTL_COUNT.value: 0
            },
            enums.RepoPinsResDictKeys.ISSUES_HELP.value: {
                enums.RepoPinsResDictKeys.TTL_COUNT.value: 0
            },
            enums.RepoPinsResDictKeys.PULL_REQUESTS.value: {
                enums.RepoPinsResDictKeys.TTL_COUNT.value: 0
            },
            enums.RepoPinsResDictKeys.OWNER.value: {
                enums.RepoPinsResDictKeys.LOGIN.value: "profile-icons"
            },
            enums.RepoPinsResDictKeys.DESCRIPTION.value: "",
            enums.RepoPinsResDictKeys.URL.value: "https://github.com/profile-icons/readme-repo-pins",
            enums.RepoPinsResDictKeys.URL_CUSTOM.value: "",
            enums.RepoPinsResDictKeys.LANGUAGE.value: {},
            enums.RepoPinsResDictKeys.IS_FORK.value: False,
            enums.RepoPinsResDictKeys.PARENT.value: {},
            enums.RepoPinsResDictKeys.IS_TEMPLATE.value: False,
            enums.RepoPinsResDictKeys.IS_ARCHIVE.value: False,
            enums.RepoPinsResDictKeys.IS_PRIVATE.value: False,
            enums.RepoPinsResDictKeys.CONTRIBUTION.value: [],
        },
    ]

    try:
        for i, tst_repo_data in enumerate(tst_input):
            if i > 0:
                log.info(
                    msg=f"Render repo pins progress: {(i / len(tst_input) * 100):.2f}% ({i}/{len(tst_input)})"
                )
            repo_pin: RepoPinImgData = RepoPinImgData.format_repo_pin_data(
                repo_data=tst_repo_data,
                user_repo_owner=test_username,
                login_username=test_username,
                login_user_name=test_username,
                login_user_id=test_user_id,
                theme_name=enums.RepoPinsImgThemeName(test_theme_name),
                bg_img=test_bg_img,
            )
            repo_pin_img: RepoPinImg = RepoPinImg(
                repo_pin_data=repo_pin, is_nllb_trans=is_nllb_trans
            )
            repo_pin_img.render()
            write_svg(svg_obj_str=repo_pin_img.svg, file_name=f"-{i + 1}")
    except ValueError:
        print(
            f"Theme '{test_theme_name}' is either not in themes.json or GenerateRepoPins.update_themes() is not used."
        )
    except (RepoPinImageThemeError, RepoPinImageMediaError) as err:
        print(err.msg)


if __name__ == "__main__":
    from utils.utils import tst_svg_parse_args

    try:
        tst_svg_render(*tst_svg_parse_args())
    except AssertionError as e:
        print(f"Error: {str(e)}")
