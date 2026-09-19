from subprocess import run
from sys import executable


def execute(command: list[str]) -> None:
    print(f"\n> {' '.join(command)}")
    run(command, check=True)


def main() -> None:
    # format
    execute(
        [
            executable,
            "-m",
            "black",
            "--fast",
            "gh_profile_repo_pins/.",
            "utils/.",
        ]
    )

    # lint
    execute(
        [
            executable,
            "-m",
            "ruff",
            "check",
            "gh_profile_repo_pins/.",
            "utils/.",
        ]
    )

    # type check
    execute(
        [
            executable,
            "-m",
            "mypy",
            "gh_profile_repo_pins",
            "utils",
        ]
    )

    print("\nAll code verifications pass.")
