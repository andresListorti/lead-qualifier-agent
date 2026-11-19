from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.agent import FixtureProvider, qualify_lead
from api.app.config import Settings
from api.app.database import make_engine, make_session_factory
from api.app.models import Lead
from api.app.schemas import LeadCreate


def seed_demo(session: Session) -> int:
    """Add missing numbered fixtures; repeat runs do not duplicate demo records."""
    added = 0
    for number in range(1, 11):
        company = f"DEMO DATA Company {number:02d}"
        if session.scalar(select(Lead.id).where(Lead.company == company)) is not None:
            continue
        payload = LeadCreate(
            name=f"DEMO DATA Person {number:02d}", company=company,
            message="DEMO DATA: We would like a demo meeting." if number % 2
            else "DEMO DATA: Exploring options for a fictional project.",
            budget=[0, 500, 1000, 5000, 10000][(number - 1) % 5],
        )
        session.add(Lead(
            **payload.model_dump(),
            qualification=qualify_lead(payload, FixtureProvider()).model_dump(),
        ))
        added += 1
    session.commit()
    return added


if __name__ == "__main__":
    factory = make_session_factory(make_engine(Settings.from_env().database_url))
    with factory() as session:
        print(f"DEMO DATA: added {seed_demo(session)} fictional leads")
