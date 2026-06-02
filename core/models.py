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


class AppConfig(db.Model):
    """Ustawienia aplikacji edytowalne przez dziekanat/admin."""

    __tablename__ = "app_config"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(100), nullable=False, unique=True)
    value = db.Column(db.String(500), nullable=False)
    label = db.Column(db.String(200))

    def __repr__(self):
        return f"<AppConfig {self.key}={self.value}>"


class DocumentWorkflow(db.Model):
    """
    Stan obiegu pojedynczego dokumentu (album + formularz) w bazie danych.

    Treść formularza nadal mieszka w `data/studenci.json`; tutaj trzymamy
    *autorytatywny* status, przypisanego recenzenta i ostatnią decyzję, dzięki
    czemu kolejki recenzentów i powiadomienia opierają się na bazie, a nie na
    pliku JSON.
    """

    __tablename__ = "document_workflow"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    album_number = db.Column(db.String(20), nullable=False)
    form_key = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="draft")
    reviewer_role = db.Column(db.String(20))
    rejection_comment = db.Column(db.Text)
    rejection_by = db.Column(db.String(200))
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    __table_args__ = (
        db.UniqueConstraint("album_number", "form_key", name="uq_workflow_doc"),
    )

    def __repr__(self):
        return f"<DocumentWorkflow {self.album_number}/{self.form_key}={self.status}>"


class DocumentLog(db.Model):
    """Dziennik zdarzeń obiegu dokumentu (append-only) – kto, co i kiedy."""

    __tablename__ = "document_log"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    album_number = db.Column(db.String(20), nullable=False)
    form_key = db.Column(db.String(10), nullable=False)
    action = db.Column(db.String(20), nullable=False)  # created/updated/submitted/approved/rejected/deleted
    actor_id = db.Column(db.Integer)
    actor_name = db.Column(db.String(200))
    actor_role = db.Column(db.String(20))
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<DocumentLog {self.album_number}/{self.form_key} {self.action}>"


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
    speciality = db.Column(db.String(400))
    study_mode = db.Column(db.String(20), default='stacjonarne')
    semester = db.Column(db.String(10))       # semestr studenta (np. "6")
    study_year = db.Column(db.String(10))     # rok studiów (np. "3")

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
