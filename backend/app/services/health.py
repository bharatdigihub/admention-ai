from sqlalchemy import text
from sqlalchemy.orm import Session


class HealthService:
    """Verifies application and database readiness."""

    def check(self, db: Session) -> dict[str, str]:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "caption_engine": "caption-proxy-v5"}
