import argparse
import getpass

from werkzeug.security import generate_password_hash

from app import app
from core.models import User, UserSession, db


def run():
    parser = argparse.ArgumentParser(description="Ustaw nowe hasło użytkownika.")
    parser.add_argument("email")
    args = parser.parse_args()

    password = getpass.getpass("Nowe hasło: ")
    confirmation = getpass.getpass("Powtórz hasło: ")
    if password != confirmation:
        raise SystemExit("Hasła nie są identyczne.")
    if len(password) < 12:
        raise SystemExit("Hasło musi mieć co najmniej 12 znaków.")

    with app.app_context():
        user = User.query.filter_by(email=args.email.lower().strip()).first()
        if user is None:
            raise SystemExit("Nie znaleziono użytkownika.")
        user.password_hash = generate_password_hash(password)
        user.failed_login_attempts = 0
        user.locked_until = None
        UserSession.query.filter_by(user_id=user.id, is_revoked=0).update(
            {"is_revoked": 1},
            synchronize_session=False,
        )
        db.session.commit()
        print(f"Hasło użytkownika {user.email} zostało zmienione.")


if __name__ == "__main__":
    run()
