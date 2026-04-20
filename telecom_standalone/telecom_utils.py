"""
Stub for tau2.domains.telecom.utils.
Points TELECOM_DB_PATH and TELECOM_USER_DB_PATH to local TOML files.
"""
from datetime import date, datetime
from pathlib import Path

_DIR = Path(__file__).parent

TELECOM_DB_PATH      = _DIR / "db.toml"
TELECOM_USER_DB_PATH = _DIR / "user_db.toml"


def get_now() -> datetime:
    return datetime(2025, 2, 25, 12, 8, 0)


def get_today() -> date:
    return date(2025, 2, 25)
