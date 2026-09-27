import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    # _env_file=None: ignore any local .env so the test only sees the (empty) environment.
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)
