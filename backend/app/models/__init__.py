# Import every model here so Base.metadata is complete when Alembic autogenerates.
from app.models.base import Base
from app.models.paper import Paper

__all__ = ["Base", "Paper"]
