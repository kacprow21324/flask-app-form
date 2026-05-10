from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class LearningEffect(db.Model):
    __tablename__ = "learning_effects"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nr = db.Column(db.Integer, nullable=False, unique=True)
    opis = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"<LearningEffect nr={self.nr}>"


class User(UserMixin, db.Model):
    """
    Konto użytkownika – mapuje tabelę `users` ze schematu bazy danych.

    Pole `is_active` to kolumna INTEGER (0/1). Flask-Login traktuje wartość
    truthy/falsy, więc 1 = aktywny, 0 = zablokowany (konto pracownicze czeka
    na zatwierdzenie przez admina).
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.Text, nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=False)
    first_name = db.Column(db.Text, nullable=False)
    last_name = db.Column(db.Text, nullable=False)
    role = db.Column(
        db.Text,
        nullable=False,
        # Dozwolone role zgodnie ze schematem bazy danych
    )
    album_number = db.Column(db.Text, unique=True)

    # SQLAlchemy InstrumentedAttribute przesłania UserMixin.is_active (property True).
    # Wartości: 1 = aktywne, 0 = oczekuje na zatwierdzenie.
    is_active = db.Column(db.Integer, nullable=False, default=1)

    email_verified = db.Column(db.Integer, nullable=False, default=0)
    last_login_at = db.Column(db.DateTime)
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)
    avatar_url = db.Column(db.Text)

    # Pola OAuth – nie istnieją w ems_schema.sql, dodane dla obsługi logowania zewnętrznego
    oauth_provider = db.Column(db.Text)   # 'microsoft' | 'google' | 'local'
    oauth_id = db.Column(db.Text)         # OID z Microsoft / sub z Google
    tenant_id = db.Column(db.Text)        # Azure tenant ID

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role}>"
