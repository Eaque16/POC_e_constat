"""Initialisation du mode démo Windows sans droits administrateur."""

from sqlalchemy import select

from econstat.database import Base, SessionLocal, engine
from econstat.models import Role, User
from econstat.services.auth import hash_password


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        demo_users = (
            ("agent.demo", "DemoAgent2026!", Role.agent),
            ("responsable.demo", "DemoResp2026!", Role.responsable),
        )
        for username, password, role in demo_users:
            exists = db.scalar(select(User).where(User.username == username))
            if not exists:
                db.add(
                    User(
                        username=username,
                        password_hash=hash_password(password),
                        role=role,
                    )
                )
        db.commit()
    print("Base SQLite locale et comptes de démonstration initialisés.")


if __name__ == "__main__":
    main()
