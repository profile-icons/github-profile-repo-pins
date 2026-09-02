from gh_profile_repo_pins.utils import (
    write_svg,
    del_imgs,
    update_md_file,
    load_themes,
    get_md_grid_pin_str,
)
from gh_profile_repo_pins.repo_pins_img.repo_pins_img_data import RepoPinImgData
from gh_profile_repo_pins.repo_pins_exceptions import RepoPinImageThemeError
from gh_profile_repo_pins.repo_pins_img.repo_pins_img_svg import RepoPinImg
from gh_profile_repo_pins.utils import Logger, get_logger
import gh_profile_repo_pins.repo_pins_enum as enums


class GenerateRepoPins:

    def __init__(
        self,
        repo_pins_data: list[dict[str, str | int | bool | dict[str, str]]],
        user_repo_owner: str,
        login_username: str,
        login_user_name: str,
        login_user_id: int | None,
        is_org: bool,
        theme: str | dict | None,
        bg_img: dict | str | None = None,
        is_nllb_trans: bool = False,
    ) -> None:
        self.__log: Logger = get_logger()
        self.update_themes()  # update the database with any new json themes not in enums.RepoPinsImgThemeName
        self.__is_nllb_trans: bool = is_nllb_trans
        self.__is_org: bool = is_org

        try:
            self.__repo_pins: list[RepoPinImgData] = [
                RepoPinImgData.format_repo_pin_data(
                    repo_data=i,
                    user_repo_owner=user_repo_owner,
                    login_username=login_username,
                    login_user_name=login_user_name,
                    login_user_id=login_user_id,
                    theme_name=self.__get_repo_theme_data(theme=theme, repo_data_i=i),
                    bg_img=self.__get_repo_bg_img_data(bg_img=bg_img, repo_data_i=i),
                )
                for i in repo_pins_data
            ]
        except ValueError:
            raise RepoPinImageThemeError(
                msg=f"Theme '{theme}' is either not in themes.json or the database is not updated with the json data."
            )

    def __get_repo_data_key(
        self, repo_data: dict | str | None, repo_data_i: dict
    ) -> str | None:
        if repo_data and isinstance(repo_data, dict):
            repo_img_key: list[str] = [
                k
                for k in repo_data.keys()
                if repo_data_i.get(enums.RepoPinsResDictKeys.NAME.value).lower()
                in k.lower()
                and k.lower()
                in (repo_data_i.get(enums.RepoPinsResDictKeys.URL.value) or "").lower()
            ]
            return repo_img_key[0] if repo_img_key else None
        return None

    def __get_repo_theme_data(
        self, theme: dict | str | None, repo_data_i: dict
    ) -> enums.RepoPinsImgThemeName | None:
        repo_theme_key: str | None = self.__get_repo_data_key(
            repo_data=theme, repo_data_i=repo_data_i
        )
        if theme and repo_theme_key:
            return enums.RepoPinsImgThemeName(theme[repo_theme_key])
        elif theme and not isinstance(theme, dict):
            return enums.RepoPinsImgThemeName(theme)
        return None

    def __get_repo_bg_img_data(
        self, bg_img: dict | str | None, repo_data_i: dict
    ) -> dict | str | None:
        if bg_img and isinstance(bg_img, dict):
            repo_img_key: str | None = self.__get_repo_data_key(
                repo_data=bg_img, repo_data_i=repo_data_i
            )
            if (
                repo_img_key
                and isinstance(bg_img.get(repo_img_key), dict)
                and bg_img.get(repo_img_key).get(enums.RepoPinsResDictKeys.IMG.value)
            ):
                return bg_img.get(repo_img_key)
            elif (
                bg_img.values()
                and not isinstance(list(bg_img.values())[0], dict)
                and bg_img.get(enums.RepoPinsResDictKeys.IMG.value)
            ):
                return bg_img.get(enums.RepoPinsResDictKeys.IMG.value)
        elif bg_img and isinstance(bg_img, str):
            return bg_img
        return None

    def __render_repo_pin_imgs(self) -> None:
        del_imgs()
        for i, repo_pin in enumerate(self.__repo_pins):
            if i > 0:
                self.__log.info(msg=f"Render repo pins progress: {(i / len(self.__repo_pins) * 100)}%.2 ({i}/{len(self.__repo_pins)})")
            repo_pin_img: RepoPinImg = RepoPinImg(repo_pin_data=repo_pin, is_nllb_trans=self.__is_nllb_trans)
            repo_pin_img.render()
            write_svg(svg_obj_str=repo_pin_img.svg, file_name=str(i))

    def __build_grid(self) -> str:
        grid_str: str = ""
        for i, repo_data in enumerate(self.__repo_pins):
            grid_str += get_md_grid_pin_str(
                file_num=i,
                repo_name=repo_data.repo_name,
                repo_url=repo_data.url,
            )
        return grid_str

    @classmethod
    def update_themes(cls) -> None:
        enums.update_enum(
            enum_cls=enums.RepoPinsImgThemeName,
            enum_dict={k.upper(): k for k in load_themes().keys()},
        )

    def grid_display(self) -> None:
        self.__render_repo_pin_imgs()
        update_md_file(update_pin_display_str=self.__build_grid(), is_org=self.__is_org)
