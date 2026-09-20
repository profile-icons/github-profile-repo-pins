from gh_profile_repo_pins.repo_pins import ReadMeRepoPins
from utils.utils import parse_args, get_logger, Logger


def gh_readme_repo_pins():
    log: Logger = get_logger()
    try:
        custom_gh_readme_repo_pins: ReadMeRepoPins = ReadMeRepoPins(*parse_args())
    except AssertionError as err:
        log.error(msg=str(err))
        exit(1)
    custom_gh_readme_repo_pins.generate()


if __name__ == "__main__":
    gh_readme_repo_pins()
