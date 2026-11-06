# app/models.py
from datetime import UTC, date, datetime

from flask_login import UserMixin
from sqlalchemy.dialects import mysql
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from . import db


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


class UsageStat(db.Model):
    __tablename__ = "usage_stat"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    period_start = db.Column(db.Date)  # first day of month (UTC)
    tokens = db.Column(
        db.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"),
        nullable=False,
        default=0,
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "period_start", name="uix_usage_month"),
    )


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
            order_by="[Message.created_at, Message.id]",
            cascade="all, delete-orphan",
            passive_deletes=True,
        ),
    )

    role = db.Column(db.String(10), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    model = db.Column(db.String(50), nullable=True)  # registry key, e.g. 'gpt-6.1-sol'
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


# Association table for ordered prompts in chains
chain_prompts = db.Table(
    "chain_prompts",
    db.Column(
        "chain_id",
        db.Integer,
        db.ForeignKey("prompt_chain.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "prompt_id",
        db.Integer,
        db.ForeignKey("prompt.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column("position", db.Integer, nullable=False),  # order in chain
)


class Prompt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    body = db.Column(db.Text, nullable=False)
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    is_staff = db.Column(db.Boolean, default=False, nullable=False)
    approved = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(tz=UTC))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(tz=UTC),
        onupdate=lambda: datetime.now(tz=UTC),
    )

    user = db.relationship("User", backref="prompts")
    tags = db.relationship("Tag", secondary="prompt_tags", backref="prompts")


class PromptChain(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    is_staff = db.Column(db.Boolean, default=False, nullable=False)
    approved = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(tz=UTC))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(tz=UTC),
        onupdate=lambda: datetime.now(tz=UTC),
    )

    user = db.relationship("User", backref="prompt_chains")
    prompts = db.relationship(
        "Prompt",
        secondary=chain_prompts,
        order_by=chain_prompts.c.position,
        backref="chains",
    )
    tags = db.relationship("Tag", secondary="chain_tags", backref="prompt_chains")


# Association table for prompt tags
prompt_tags = db.Table(
    "prompt_tags",
    db.Column(
        "prompt_id",
        db.Integer,
        db.ForeignKey("prompt.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "tag_id",
        db.Integer,
        db.ForeignKey("tag.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# Optional: separate tags for chains
chain_tags = db.Table(
    "chain_tags",
    db.Column(
        "chain_id",
        db.Integer,
        db.ForeignKey("prompt_chain.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "tag_id",
        db.Integer,
        db.ForeignKey("tag.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


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
    return db.session.get(Conversation, conversation_id)


def get_conversation_messages(conversation_id):
    # id breaks created_at ties (one-second resolution on MySQL DATETIME).
    messages = (
        Message.query.filter_by(conversation_id=conversation_id)
        .order_by(Message.created_at, Message.id)
        .all()
    )
    return messages


def get_conversation_messages_by_role(conversation_id, role):
    messages = (
        Message.query.filter_by(conversation_id=conversation_id, role=role)
        .order_by(Message.created_at, Message.id)
        .all()
    )
    return messages


def update_conversation_title(conversation_id, title):
    conversation = db.session.get(Conversation, conversation_id)
    if conversation:
        conversation.title = title
        db.session.commit()
        return True
    return False


def delete_conversation(conversation_id):
    conversation = db.session.get(Conversation, conversation_id)
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


def search_conversations_by_message(user_id, query, limit_per_convo=1, max_convos=50):
    """
    Returns (conversations, convo_to_msg), where:
      - conversations: list of Conversation objects, sorted by most recent message
        matching search
      - convo_to_msg: dict {conversation_id: [Message, ...]}, with up to
        `limit_per_convo` matching messages per convo
    """
    from sqlalchemy.orm import aliased

    # Find all messages in user's conversations that match search
    # (case-insensitive, partial)
    MessageAlias = aliased(Message)
    matches = (
        db.session.query(MessageAlias)
        .join(Conversation, MessageAlias.conversation_id == Conversation.id)
        .filter(
            Conversation.user_id == user_id, MessageAlias.content.ilike(f"%{query}%")
        )
        .order_by(MessageAlias.created_at.desc())
        .all()
    )

    # Collect up to limit_per_convo per conversation
    convo_to_msgs = {}
    for msg in matches:
        lst = convo_to_msgs.setdefault(msg.conversation_id, [])
        if len(lst) < limit_per_convo:
            lst.append(msg)
        if len(convo_to_msgs) >= max_convos:
            break

    # Get unique conversations (in order of most recent match)
    conversation_ids = list(convo_to_msgs.keys())
    if not conversation_ids:
        return [], {}

    conversations = (
        Conversation.query.filter(Conversation.id.in_(conversation_ids))
        .order_by(Conversation.created_at.desc())
        .all()
    )
    # For template convenience, map by id (could be sparse ordering if you want
    # to preserve match recency)
    return conversations, convo_to_msgs


# ---------------------------------------------------------------------------
# Monthly token usage
# ---------------------------------------------------------------------------


def usage_period_start(now: datetime | None = None) -> date:
    """First day of the current month in UTC: the key of a ``UsageStat`` row."""
    return (now or datetime.now(tz=UTC)).date().replace(day=1)


def add_usage_tokens(user_id: int, tokens: int, period_start: date) -> None:
    """Atomically add ``tokens`` to the user's counter for ``period_start``.

    One INSERT ... ON CONFLICT/ON DUPLICATE KEY statement per dialect, so concurrent
    requests cannot lose an increment. Does not commit: the caller decides the
    transaction (``AIStreamer`` commits it together with the turn's messages).
    """
    if tokens <= 0:
        return
    values = {"user_id": user_id, "period_start": period_start, "tokens": tokens}
    dialect = db.session.get_bind(mapper=UsageStat.__mapper__).dialect.name
    if dialect in ("mysql", "mariadb"):
        stmt = mysql_insert(UsageStat).values(**values)
        stmt = stmt.on_duplicate_key_update(tokens=UsageStat.tokens + tokens)
    elif dialect in ("sqlite", "postgresql"):
        insert = sqlite_insert if dialect == "sqlite" else postgresql_insert
        stmt = insert(UsageStat).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "period_start"],
            set_={"tokens": UsageStat.tokens + tokens},
        )
    else:
        raise NotImplementedError(f"No usage upsert for dialect {dialect!r}")
    db.session.execute(stmt)


def get_usage_tokens(user_id: int, period_start: date) -> int:
    stat = UsageStat.query.filter_by(user_id=user_id, period_start=period_start).first()
    return stat.tokens if stat else 0
