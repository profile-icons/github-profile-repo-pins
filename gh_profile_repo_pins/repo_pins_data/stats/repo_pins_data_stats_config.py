from re import I, Pattern, compile


class RepoPinStatsConfig:

    TMP_DIR: str = "tmp_git"
    IS_PROC_ERR: bool = True
    MAX_WORKERS: int = 1
    GIT_PROC_TO_S: int = 180
    BLOB_PREFETCH_BATCH_SIZE: int = 200

    COMMIT_LBL: str = "@@COMMIT@@"
    AUTH_LBL: str = "@@AUTHOR@@"
    RAW_AUTH_LBL: str = "@@RAW_AUTHOR@@"
    CO_AUTH_LBL: str = "Co-authored-by:"

    IGNORE_PATH: frozenset[str] = frozenset(
        {
            ".gradle",
            ".idea",
            ".ipynb_checkpoints",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".tox",
            ".venv",
            ".vscode",
            "__pycache__",
            "build",
            "coverage",
            "dist",
            "htmlcov",
            "node_modules",
            "out",
            "target",
            "vendor",
            "trainedagents",
            "checkpoints",
            "wandb",
            "mlruns",
        }
    )
    IGNORE_BASE: frozenset[str] = frozenset(
        {
            ".coverage",
            ".ds_store",
            "cargo.lock",
            "composer.lock",
            "gemfile.lock",
            "package-lock.json",
            "pipfile.lock",
            "pnpm-lock.yaml",
            "poetry.lock",
            "thumbs.db",
            "yarn.lock",
        }
    )
    IGNORE_SFX: tuple[str, ...] = (
        ".class",
        ".iml",
        ".log",
        ".min.css",
        ".min.js",
        ".pyc",
        ".pyo",
        ".sourcemap",
    )
    IGNORE_SFX_BIN: tuple[str, ...] = (
        ".7z",
        ".avi",
        ".bin",
        ".bmp",
        ".db",
        ".dll",
        ".doc",
        ".docx",
        ".dylib",
        ".eot",
        ".exe",
        ".gif",
        ".gz",
        ".ico",
        ".jar",
        ".jpeg",
        ".jpg",
        ".m4a",
        ".mov",
        ".mp3",
        ".mp4",
        ".ods",
        ".odt",
        ".ogg",
        ".otf",
        ".pdf",
        ".png",
        ".ppt",
        ".pptx",
        ".rar",
        ".so",
        ".sqlite",
        ".sqlite3",
        ".tar",
        ".tif",
        ".tiff",
        ".ttf",
        ".wav",
        ".webm",
        ".webp",
        ".woff",
        ".woff2",
        ".xls",
        ".xlsx",
        ".xz",
        ".zip",
        ".pkl",
        ".pickle",
        ".npy",
        ".npz",
        ".pt",
        ".pth",
        ".ckpt",
        ".h5",
        ".hdf5",
        ".onnx",
        ".joblib",
        ".parquet",
        ".feather",
        ".arrow",
    )

    AUTO_BOT_NAME: frozenset[str] = frozenset(
        {"cursor agent", "dependabot", "github actions", "renovate bot"}
    )
    AUTO_BOT_EMAIL: frozenset[str] = frozenset(
        {"cursoragent@cursor.com", "github-actions[bot]@users.noreply.github.com"}
    )

    COMMIT_REG: Pattern[str] = compile(
        pattern=r"^{}\s+([0-9a-f]+)\s+([0-9a-f]+)(?:\s+([0-9a-f ]+))?\s*$".format(
            COMMIT_LBL
        ),
        flags=I,
    )
    AUTH_REG: Pattern[str] = compile(
        pattern=r"^{}\s+(.+?)\s*<([^>]+)>\s*$".format(AUTH_LBL)
    )
    RAW_AUTH_REG: Pattern[str] = compile(
        pattern=r"^{}\s+(.+?)\s*<([^>]+)>\s*$".format(RAW_AUTH_LBL)
    )
    CO_AUTH_REG: Pattern[str] = compile(
        pattern=r"^\s*{}\s*(.+?)\s*<([^>]+)>\s*$".format(CO_AUTH_LBL), flags=I
    )
    RAW_DIFF_REG: Pattern[str] = compile(
        pattern=(
            r"^:[0-7]{6}\s+[0-7]{6}\s+([0-9a-f]+)\s+([0-9a-f]+)\s+"
            r"([A-Z])[0-9]*\t(.+)$"
        ),
        flags=I,
    )
    CODE_TOKEN_REG: Pattern[str] = compile(
        r""""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|[A-Za-z_$][A-Za-z0-9_$]*|\d+(?:\.\d+)?|\S"""
    )
