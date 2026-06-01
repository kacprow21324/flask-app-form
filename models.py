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


class Specialty(db.Model):
    __tablename__ = "specialties"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(400), nullable=False, unique=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<Specialty {self.name[:40]}>"


class Attachment(db.Model):
    """Metadane załącznika + kto go zatwierdza (reviewer_role=None → brak recenzenta)."""

    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(10), nullable=False, unique=True)
    nr = db.Column(db.String(5), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    reviewer_role = db.Column(db.String(20))
    reviewer_label = db.Column(db.String(100))
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<Attachment {self.key}>"


class RoleFormAccess(db.Model):
    """Która rola może tworzyć/edytować który formularz."""

    __tablename__ = "role_form_access"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role = db.Column(db.String(20), nullable=False)
    form_key = db.Column(db.String(10), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("role", "form_key", name="uq_role_form"),
    )

    def __repr__(self):
        return f"<RoleFormAccess {self.role}:{self.form_key}>"


class StudentWorkflowStep(db.Model):
    """Kolejne kroki przewodnika dla studenta na dashboardzie."""

    __tablename__ = "student_workflow_steps"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    step = db.Column(db.Integer, nullable=False, unique=True)
    key = db.Column(db.String(10), nullable=False, unique=True)
    nr = db.Column(db.String(5), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    when_label = db.Column(db.String(50), nullable=False)
    hint = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"<StudentWorkflowStep {self.step}:{self.key}>"


class SurveyQuestion(db.Model):
    __tablename__ = "survey_questions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nr = db.Column(db.Integer, nullable=False, unique=True)
    text = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"<SurveyQuestion nr={self.nr}>"


class SurveyOption(db.Model):
    __tablename__ = "survey_options"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sort_order = db.Column(db.Integer, nullable=False)
    label = db.Column(db.String(100), nullable=False, unique=True)

    def __repr__(self):
        return f"<SurveyOption {self.label}>"


class FormField(db.Model):
    """Nazwy pól danego formularza – używane w dropdown recenzenta."""

    __tablename__ = "form_fields"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    form_key = db.Column(db.String(10), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    field_name = db.Column(db.String(200), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("form_key", "field_name", name="uq_form_field"),
    )

    def __repr__(self):
        return f"<FormField {self.form_key}:{self.field_name}>"


class User(UserMixin, db.Model):
    """
    Konto użytkownika – mapuje tabelę `users` ze schematu bazy danych.

    Pole `is_active` to kolumna INTEGER (0/1). Flask-Login traktuje wartość
    truthy/falsy, więc 1 = aktywny, 0 = zablokowany (konto pracownicze czeka
    na zatwierdzenie przez admina).
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    album_number = db.Column(db.String(20), unique=True)

    is_active = db.Column(db.Integer, nullable=False, default=1)

    email_verified = db.Column(db.Integer, nullable=False, default=0)
    last_login_at = db.Column(db.DateTime)
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)
    avatar_url = db.Column(db.String(500))

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
