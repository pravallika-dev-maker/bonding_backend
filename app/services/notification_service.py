from sqlalchemy.orm import Session
from ..models.notification import Notification

def create_notification(db: Session, recipient_id: int, notification_type: str, title: str, body: str = None):
    notif = Notification(
        recipient_id=recipient_id, 
        notification_type=notification_type,
        title=title, 
        body=body
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif
