from flask_login import UserMixin
from . import db
from datetime import datetime, UTC


class User(UserMixin, db.Model):
    # primary keys are required by SQLAlchemy
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(255))
    name = db.Column(db.String(1000))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(tz=UTC))
    last_login = db.Column(db.DateTime)
    stripe_customer_id = db.Column(db.String(100), nullable=True)
    subscription_status = db.Column(db.String(50), nullable=True)
    # e.g., "pro_monthly" or Stripe price ID
    subscription_plan = db.Column(db.String(100), nullable=True)
    subscription_start = db.Column(db.DateTime, nullable=True)
    # For canceled or expired subscriptions
    subscription_end = db.Column(db.DateTime, nullable=True)
    conversations = db.relationship(
        "Conversation",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    verified = db.Column(db.Boolean, default=False)
    preferences = db.Column(db.JSON, nullable=True)


class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    # Optional, can be first message
    title = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(tz=UTC))


message_tags = db.Table(
    "message_tags",
    db.Column(
        "message_id",
        db.Integer,
        db.ForeignKey("message.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "tag_id",
        db.Integer,
        db.ForeignKey("tag.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )

    user = db.relationship("User", backref=db.backref("tags", lazy=True))
    __table_args__ = (db.UniqueConstraint("user_id", "name", name="uix_user_tag_name"),)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    conversation = db.relationship(
        "Conversation",
        backref=db.backref(
            "messages",
            order_by="Message.created_at",
            cascade="all, delete-orphan",
            passive_deletes=True,
        ),
    )

    role = db.Column(db.String(10), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    model = db.Column(db.String(50), nullable=True)  # e.g., 'gpt-3.5-turbo'
    tags = db.relationship("Tag", secondary=message_tags, backref="messages")
    is_favorite = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(tz=UTC))


class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    type = db.Column(db.String(20), nullable=False)  # 'support', 'feature'
    subject = db.Column(db.String(255))
    status = db.Column(
        db.String(20), default="open"
    )  # 'open', 'pending', 'resolved', 'closed'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(tz=UTC))
    closed_at = db.Column(db.DateTime, nullable=True)
    last_updated = db.Column(
        db.DateTime,
        default=lambda: datetime.now(tz=UTC),
        onupdate=lambda: datetime.now(tz=UTC),
    )
    messages = db.relationship(
        "TicketMessage",
        backref="ticket",
        cascade="all, delete-orphan",
        order_by="TicketMessage.created_at",
        lazy=True,
    )
    user = db.relationship("User", backref="tickets", foreign_keys=[user_id])

    def close(self):
        self.status = "closed"
        self.closed_at = datetime.now(tz=UTC)


class TicketMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(
        db.Integer, db.ForeignKey("ticket.id", ondelete="CASCADE"), nullable=False
    )
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    sender_type = db.Column(db.String(20), nullable=False)  # 'user', 'admin', 'ai'
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(tz=UTC))


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Sender (admin/staff) user, nullable for system messages
    sent_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    # Recipient user; NULL means broadcast to all users
    for_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    # Optional: Related ticket (for ticket updates)
    ticket_id = db.Column(db.Integer, db.ForeignKey("ticket.id"), nullable=True)

    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # e.g., 'system', 'ticket'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(tz=UTC))

    # Relationships for easier navigation
    sender = db.relationship(
        "User", foreign_keys=[sent_by], backref="sent_notifications"
    )
    recipient = db.relationship(
        "User", foreign_keys=[for_user_id], backref="received_notifications"
    )
    ticket = db.relationship("Ticket", backref="notifications")


class NotificationRead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(
        db.Integer, db.ForeignKey("notification.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    read_at = db.Column(db.DateTime, default=lambda: datetime.now(tz=UTC))

    # Enforce uniqueness per user-notification
    __table_args__ = (
        db.UniqueConstraint("notification_id", "user_id", name="uix_notification_user"),
    )

    notification = db.relationship("Notification", backref="reads")
    user = db.relationship("User", backref="notification_reads")
    archived = db.Column(db.Boolean, default=False, nullable=False)


def create_conversation(user_id, title=None):
    new_conversation = Conversation(user_id=user_id, title=title)
    db.session.add(new_conversation)
    db.session.commit()
    return new_conversation


def create_message(conversation_id, role, content, model):
    new_message = Message(
        conversation_id=conversation_id, role=role, content=content, model=model
    )
    db.session.add(new_message)
    db.session.commit()
    return new_message


def get_user_conversations(user_id):
    conversations = Conversation.query.filter_by(user_id=user_id).all()
    return conversations


def get_conversation(conversation_id):
    conversation = Conversation.query.get(conversation_id)
    return conversation


def get_conversation_messages(conversation_id):
    messages = (
        Message.query.filter_by(conversation_id=conversation_id)
        .order_by(Message.created_at)
        .all()
    )
    return messages


def get_conversation_messages_by_role(conversation_id, role):
    messages = (
        Message.query.filter_by(conversation_id=conversation_id, role=role)
        .order_by(Message.created_at)
        .all()
    )
    return messages


def update_conversation_title(conversation_id, title):
    conversation = Conversation.query.get(conversation_id)
    if conversation:
        conversation.title = title
        db.session.commit()
        return True
    return False


def delete_conversation(conversation_id):
    conversation = Conversation.query.get(conversation_id)
    if conversation:
        db.session.delete(conversation)
        db.session.commit()
        return True
    return False


# All unread notifications for a user
def get_unread_notifications(user_id):
    NotificationModel = Notification
    NotificationReadModel = NotificationRead

    # Subquery: notifications user has read
    read_subquery = db.session.query(NotificationReadModel.notification_id).filter_by(
        user_id=user_id
    )
    # All notifications (broadcast or targeted) not read by user
    unread = NotificationModel.query.filter(
        (
            (NotificationModel.for_user_id.is_(None))
            | (NotificationModel.for_user_id == user_id)
        ),
        ~NotificationModel.id.in_(read_subquery),
    ).order_by(NotificationModel.created_at.desc())
    return unread.all()
