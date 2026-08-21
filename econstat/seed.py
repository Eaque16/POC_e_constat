from sqlalchemy import select

from econstat.database import SessionLocal
from econstat.models import Role, User
from econstat.services.auth import hash_password


def main():
    with SessionLocal() as db:
        for username, password, role in [
            ("agent.demo", "DemoAgent2026!", Role.agent),
            ("responsable.demo", "DemoResp2026!", Role.responsable),
        ]:
            if not db.scalar(select(User).where(User.username == username)):
                db.add(User(username=username, password_hash=hash_password(password), role=role))
        db.commit()
    print("Utilisateurs de démonstration créés.")


if __name__ == "__main__":
    main()
