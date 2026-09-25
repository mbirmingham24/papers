from alembic import command
from alembic.config import Config


def test_migrations_upgrade_downgrade_upgrade(alembic_config: Config) -> None:
    # Catches downgrades that are broken or leave something behind.
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")


def test_models_match_migrations(alembic_config: Config) -> None:
    # Fails if a model was changed without generating a migration for it.
    command.upgrade(alembic_config, "head")
    command.check(alembic_config)
