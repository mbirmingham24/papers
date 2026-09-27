import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize("name", ["DATABASE_URL", "REDIS_URL"])
def test_connection_urls_are_required(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(name, raising=False)

    # _env_file=None: ignore any local .env so the test only sees the environment.
    with pytest.raises(ValidationError, match=name.lower()):
        Settings(_env_file=None)
