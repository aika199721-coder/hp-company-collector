"""ApplicationFactory composition tests without network access."""

from pathlib import Path

from application.config import ApplicationConfigLoader
from application.factory import ApplicationFactory
from storage.sqlite import SCHEMA_VERSION
from tests.unit.test_application_config import copy_config


class FakeFetcher:
    """No-network marker dependency."""


def test_factory_initializes_schema_and_accepts_overrides(tmp_path: Path) -> None:
    config = ApplicationConfigLoader({}).load(copy_config(tmp_path))
    fake = FakeFetcher()

    components = ApplicationFactory(config, overrides={"fetcher": fake}).build()

    assert components.fetcher is fake
    with components.database.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
