from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_config import (
    RepoPinStatsConfig,
)
from gh_profile_repo_pins.repo_pins_data.stats.repo_pins_data_stats_models import (
    AuthorId,
)
from pathlib import PurePosixPath


class RepoPinStatsPolicy:

    @classmethod
    def cred_hist_path_specs(cls, is_exclude_nb: bool = False) -> list[str]:
        path_specs: list[str] = ["."]
        for suffix in RepoPinStatsConfig.IGNORE_SFX_BIN + RepoPinStatsConfig.IGNORE_SFX:
            path_specs.append(f":(exclude,icase,glob)**/*{suffix}")
        for part in RepoPinStatsConfig.IGNORE_PATH:
            path_specs.append(f":(exclude,icase,glob)**/{part}/**")
        for basename in RepoPinStatsConfig.IGNORE_BASE:
            path_specs.append(f":(exclude,icase,glob)**/{basename}")
        path_specs.append(":(exclude,icase,glob)**/useractionhistory*.xml")
        if is_exclude_nb:
            path_specs.append(":(exclude,icase,glob)**/*.ipynb")
        return path_specs

    @classmethod
    def is_cred_path(cls, path: str) -> bool:
        pp: PurePosixPath = PurePosixPath(path.replace("\\", "/").removeprefix("./"))
        basename: str = pp.name.casefold()

        if {part.casefold() for part in pp.parts[:-1]} & RepoPinStatsConfig.IGNORE_PATH:
            return False
        if basename in RepoPinStatsConfig.IGNORE_BASE:
            return False
        if basename.startswith("useractionhistory") and basename.endswith(".xml"):
            return False
        return not basename.endswith(
            RepoPinStatsConfig.IGNORE_SFX + RepoPinStatsConfig.IGNORE_SFX_BIN
        )

    @staticmethod
    def is_nb_path(path: str | None) -> bool:
        return bool(path and path.casefold().endswith(".ipynb"))

    @classmethod
    def is_cred_patch_path(cls, path: str) -> bool:
        return cls.is_cred_path(path=path) and not cls.is_nb_path(path=path)

    @classmethod
    def is_auto_id(cls, auth_id: AuthorId) -> bool:
        id_names, id_emails = auth_id
        id_names = {name.casefold().strip() for name in id_names}
        id_emails = {email.casefold().strip() for email in id_emails}
        # if id_names & RepoPinStatsConfig.AUTO_BOT_NAME:
        #     return True
        # if id_emails & RepoPinStatsConfig.AUTO_BOT_EMAIL:
        #     return True
        return any(name.endswith("[bot]") for name in id_names) or any(
            "[bot]" in email.split("@", 1)[0] for email in id_emails
        )
