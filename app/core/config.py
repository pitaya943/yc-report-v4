"""Settings: read once from the environment, every problem reported together.

Nothing else in the program reads environment variables.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from psycopg.conninfo import conninfo_to_dict

APP_ENVS = ("development", "test", "production")
# The clock offset is for trying timeouts by hand. 366 days is more than that
# needs and far below what a datetime can hold.
MAX_CLOCK_OFFSET_MINUTES = 366 * 24 * 60
PASSWORD_HASH_PROFILES = ("standard", "fast")


class ConfigError(Exception):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("設定有問題：\n" + "\n".join(f"- {p}" for p in problems))


@dataclass(frozen=True)
class Settings:
    database_url: str
    app_env: str
    password_hash_profile: str
    trusted_proxy_hops: int
    clock_offset_minutes: int
    storage_configured: bool
    bank_key_configured: bool

    def describe(self) -> list[str]:
        """One line per setting, without any secret value."""

        def configured(value: bool) -> str:
            return "已設定" if value else "未設定"

        return [
            "DATABASE_URL：已設定",
            f"APP_ENV：{self.app_env}",
            f"PASSWORD_HASH_PROFILE：{self.password_hash_profile}",
            f"TRUSTED_PROXY_HOPS：{self.trusted_proxy_hops}",
            f"CLOCK_OFFSET_MINUTES：{self.clock_offset_minutes}",
            f"STORAGE_BACKEND：{configured(self.storage_configured)}",
            f"BANK_KEY：{configured(self.bank_key_configured)}",
        ]


def load_settings(environ: Mapping[str, str]) -> Settings:
    problems: list[str] = []

    def text(name: str) -> str:
        return environ.get(name, "").strip()

    def choice(name: str, allowed: tuple[str, ...]) -> str:
        value = text(name) or allowed[0]
        if value not in allowed:
            problems.append(f"{name}：必須是 {'、'.join(allowed)} 其中之一")
        return value

    def integer(name: str, *, minimum: int | None = None) -> int:
        try:
            value = int(text(name) or "0")
        except ValueError:
            problems.append(f"{name}：必須是整數")
            return 0
        if minimum is not None and value < minimum:
            problems.append(f"{name}：不可小於 {minimum}")
        return value

    database_url = text("DATABASE_URL")
    if not database_url:
        problems.append("DATABASE_URL：缺少（必要）")
    else:
        try:
            conninfo_to_dict(database_url)
        except Exception:
            problems.append("DATABASE_URL：不是合法的 PostgreSQL 連線字串")

    app_env = choice("APP_ENV", APP_ENVS)
    profile = choice("PASSWORD_HASH_PROFILE", PASSWORD_HASH_PROFILES)
    hops = integer("TRUSTED_PROXY_HOPS", minimum=0)
    offset = integer("CLOCK_OFFSET_MINUTES")
    if abs(offset) > MAX_CLOCK_OFFSET_MINUTES:
        problems.append(
            f"CLOCK_OFFSET_MINUTES：必須在 -{MAX_CLOCK_OFFSET_MINUTES} 到 {MAX_CLOCK_OFFSET_MINUTES} 之間（366 天）"
        )

    if app_env == "production":
        if profile == "fast":
            problems.append("PASSWORD_HASH_PROFILE：production 不可使用 fast")
        if offset != 0:
            problems.append("CLOCK_OFFSET_MINUTES：production 必須是 0")

    if problems:
        raise ConfigError(problems)

    return Settings(
        database_url=database_url,
        app_env=app_env,
        password_hash_profile=profile,
        trusted_proxy_hops=hops,
        clock_offset_minutes=offset,
        storage_configured=bool(text("STORAGE_BACKEND")),
        bank_key_configured=bool(text("BANK_KEY")),
    )
