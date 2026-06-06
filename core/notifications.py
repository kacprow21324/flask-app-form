from datetime import datetime

from core.models import Notification, User, db


def notify_user(
    user,
    notification_type,
    title,
    message,
    link,
    *,
    entity_type=None,
    entity_id=None,
    dedupe_key=None,
    commit=False,
):
    if user is None:
        return None
    existing = (
        Notification.query.filter_by(dedupe_key=dedupe_key).first()
        if dedupe_key
        else None
    )
    if existing:
        existing.title = title
        existing.message = message
        existing.link = link
        existing.is_read = 0
        existing.read_at = None
        existing.created_at = datetime.utcnow()
        notification = existing
    else:
        notification = Notification(
            recipient_id=user.id,
            type=notification_type,
            title=title,
            message=message,
            link=link,
            related_entity_type=entity_type,
            related_entity_id=entity_id,
            dedupe_key=dedupe_key,
        )
        db.session.add(notification)
    if commit:
        db.session.commit()
    return notification


def notify_role(role, *args, commit=False, **kwargs):
    notifications = [
        notify_user(user, *args, commit=False, **kwargs)
        for user in User.query.filter_by(role=role, is_active=1).all()
    ]
    if commit:
        db.session.commit()
    return notifications


def unread_for(user):
    return (
        Notification.query.filter_by(recipient_id=user.id, is_read=0)
        .order_by(Notification.created_at.desc())
        .all()
    )
