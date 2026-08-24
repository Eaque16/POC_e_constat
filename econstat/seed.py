from sqlalchemy import select
from sqlalchemy.orm import Session

from econstat.database import SessionLocal
from econstat.models import Role, User
from econstat.services.auth import hash_password

DEMO_USERS = (
    ("agent.demo", "DemoAgent2026!", Role.agent),
    ("responsable.demo", "DemoResp2026!", Role.responsable),
)


def seed_demo_users(db: Session) -> int:
    """Crée uniquement les comptes de démonstration absents."""
    created = 0
    for username, password, role in DEMO_USERS:
        if not db.scalar(select(User).where(User.username == username)):
            db.add(User(username=username, hashed_password=hash_password(password), role=role))
            created += 1
    db.commit()
    return created


def main():
    with SessionLocal() as db:
        created = seed_demo_users(db)
    print(f"Utilisateurs de démonstration créés : {created}.")


if __name__ == "__main__":
    main()
