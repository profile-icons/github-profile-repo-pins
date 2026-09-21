from utils.utils import (
    Logger,
    del_imgs,
    get_logger,
    get_md_grid_pin_str,
    load_themes,
    update_md_file,
    write_svg,
)
from gh_profile_repo_pins.repo_pins_img.repo_pins_img_data import RepoPinImgData
from gh_profile_repo_pins.repo_pins_exceptions import RepoPinImageThemeError
from gh_profile_repo_pins.repo_pins_img.repo_pins_img_svg import RepoPinImg
import gh_profile_repo_pins.repo_pins_enum as enums
from typing import Any


class GenerateRepoPins:

    def __init__(
        self,
        repo_pins_data: list[dict[str, Any]],
        user_repo_owner: str,
        login_username: str,
        login_user_name: str,
        login_user_id: int | None,
        is_org: bool,
        theme: str | dict | None,
        bg_img: dict | str | None = None,
        is_translate: bool = False,
        is_nllb_trans: bool = False,
    ) -> None:
        self.__log: Logger = get_logger()
        self.update_themes()
        self.__is_translate: bool = is_translate
        self.__is_nllb_trans: bool = is_nllb_trans
        self.__is_org: bool = is_org

        try:
            self.__repo_pins: list[RepoPinImgData] = [
                RepoPinImgData.format_repo_pin_data(
                    repo_data=repo_data,
                    user_repo_owner=user_repo_owner,
                    login_username=login_username,
                    login_user_name=login_user_name,
                    login_user_id=login_user_id,
                    theme_name=self.__get_repo_theme_data(theme, repo_data),
                    bg_img=self.__get_repo_bg_img_data(bg_img, repo_data),
                )
                for repo_data in repo_pins_data
            ]
        except ValueError:
            raise RepoPinImageThemeError(
                msg=f"Theme '{theme}' is either not in themes.json or the database is not updated with the json data."
            )

    @staticmethod
    def __get_repo_data_key(
        repo_data: dict | str | None, repo_data_i: dict
    ) -> str | None:
        if not isinstance(repo_data, dict) or not repo_data:
            return None
        repo_name: str | None = repo_data_i.get(enums.RepoPinsResDictKeys.NAME.value)
        repo_url: str | None = repo_data_i.get(enums.RepoPinsResDictKeys.URL.value)
        if not isinstance(repo_name, str) or not isinstance(repo_url, str):
            return None
        repo_name, repo_url = repo_name.lower(), repo_url.lower()
        return next(
            (
                str(key)
                for key in repo_data
                if repo_name
                and repo_url
                and repo_name in str(key).lower()
                and str(key).lower() in repo_url
            ),
            None,
        )

    def __get_repo_theme_data(
        self, theme: dict | str | None, repo_data_i: dict
    ) -> enums.RepoPinsImgThemeName | None:
        if not isinstance(theme, dict):
            return enums.RepoPinsImgThemeName(theme) if theme else None
        key: str | None = self.__get_repo_data_key(
            repo_data=theme, repo_data_i=repo_data_i
        )
        val: str | None = theme.get(key) if key else None
        return enums.RepoPinsImgThemeName(val) if isinstance(val, str) else None

    def __get_repo_bg_img_data(
        self, bg_img: dict | str | None, repo_data_i: dict
    ) -> dict | str | None:
        if isinstance(bg_img, str):
            return bg_img if bg_img else None
        if not isinstance(bg_img, dict) or not bg_img:
            return None

        key: str | None = self.__get_repo_data_key(
            repo_data=bg_img, repo_data_i=repo_data_i
        )
        repo_img: dict | None = bg_img.get(key) if key else None
        if isinstance(repo_img, dict) and repo_img.get(
            enums.RepoPinsResDictKeys.IMG.value
        ):
            return repo_img

        if not isinstance(next(iter(bg_img.values())), dict):
            return bg_img.get(enums.RepoPinsResDictKeys.IMG.value)
        return None

    def __render_repo_pin_imgs(self) -> None:
        del_imgs()
        total_pins: int = len(self.__repo_pins)
        for i, repo_pin in enumerate[RepoPinImgData](self.__repo_pins):
            if i:
                self.__log.info(
                    msg=f"Render repo pins progress: {(i / total_pins * 100):.2f}% ({i}/{total_pins})"
                )
            repo_pin_img: RepoPinImg = RepoPinImg(
                repo_pin_data=repo_pin,
                is_translate=self.__is_translate,
                is_nllb_trans=self.__is_nllb_trans,
            )
            repo_pin_img.render()
            write_svg(svg_obj_str=repo_pin_img.svg, file_name=str(i))

    def __build_grid(self) -> str:
        return "".join(
            get_md_grid_pin_str(file_num=i, repo_name=repo.repo_name, repo_url=repo.url)
            for i, repo in enumerate[RepoPinImgData](self.__repo_pins)
        )

    @classmethod
    def update_themes(cls) -> None:
        enums.update_enum(
            enum_cls=enums.RepoPinsImgThemeName,
            enum_dict={key.upper(): key for key in load_themes()},
        )

    def grid_display(self) -> None:
        self.__render_repo_pin_imgs()
        update_md_file(update_pin_display_str=self.__build_grid(), is_org=self.__is_org)
