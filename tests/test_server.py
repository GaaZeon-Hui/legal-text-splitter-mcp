"""Tests for the MCP server module — tool wrappers and formatting."""
import os
import sys
import pytest

# Ensure the package is importable
_PKG = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from legal_text_splitter import __version__


class TestPackageMetadata:
    """Basic package integrity checks."""

    def test_version_string(self):
        """Package should expose __version__."""
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_version_format(self):
        """Version should be semver-like (X.Y.Z)."""
        parts = __version__.split('.')
        assert len(parts) == 3
        for p in parts:
            assert p.isdigit(), f'Version part "{p}" should be numeric'


class TestConfig:
    """DB config from environment variables."""

    def test_get_db_config_defaults(self):
        """get_db_config returns dict with expected keys."""
        from legal_text_splitter.config import get_db_config
        cfg = get_db_config()
        assert isinstance(cfg, dict)
        for key in ('host', 'port', 'user', 'password', 'database'):
            assert key in cfg

    def test_default_host_localhost(self):
        """Default host is localhost when env var not set."""
        from legal_text_splitter.config import get_db_config
        cfg = get_db_config()
        assert cfg['host'] == 'localhost'

    def test_env_var_override(self, monkeypatch):
        """Environment variables override defaults."""
        monkeypatch.setenv('LEGAL_DB_HOST', '192.168.1.100')
        monkeypatch.setenv('LEGAL_DB_PORT', '3307')
        from legal_text_splitter.config import get_db_config
        cfg = get_db_config()
        assert cfg['host'] == '192.168.1.100'
        assert cfg['port'] == 3307

    def test_check_db_configured_default(self):
        """Default config should NOT be considered configured."""
        from legal_text_splitter.config import check_db_configured
        assert check_db_configured() is False

    def test_check_db_configured_custom(self, monkeypatch):
        """Custom host + password IS considered configured."""
        monkeypatch.setenv('LEGAL_DB_HOST', 'db.example.com')
        monkeypatch.setenv('LEGAL_DB_PASSWORD', 'secret')
        from legal_text_splitter.config import check_db_configured
        assert check_db_configured() is True
