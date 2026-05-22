"""DB configuration from environment variables."""
import os


def get_db_config() -> dict:
    """Build DB connection dict from environment variables.

    Returns a dict with defaults for local development.
    All values can be overridden via env vars.
    """
    return {
        "host": os.environ.get("LEGAL_DB_HOST", "localhost"),
        "port": int(os.environ.get("LEGAL_DB_PORT", "3306")),
        "user": os.environ.get("LEGAL_DB_USER", "root"),
        "password": os.environ.get("LEGAL_DB_PASSWORD", ""),
        "database": os.environ.get("LEGAL_DB_NAME", "legal_db"),
    }


def check_db_configured() -> bool:
    """Return True if DB credentials appear to be configured (non-default)."""
    cfg = get_db_config()
    return bool(cfg["host"] != "localhost" and cfg["password"])
