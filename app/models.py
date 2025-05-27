from flask_login import UserMixin, current_user
from . import db
from datetime import datetime


class User(UserMixin, db.Model):
    # primary keys are required by SQLAlchemy
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(255))
    name = db.Column(db.String(1000))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_login = db.Column(db.DateTime)


class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship(
        'User', backref=db.backref('conversations', lazy=True))
    # Optional, can be first message
    title = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey(
        'conversation.id', ondelete='CASCADE'), nullable=False)
    conversation = db.relationship(
        'Conversation',
        backref=db.backref(
            'messages',
            order_by='Message.created_at',
            cascade='all, delete-orphan',
            passive_deletes=True
        )
    )

    role = db.Column(db.String(10), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)


def create_conversation(user_id, title=None):
    new_conversation = Conversation(user_id=user_id, title=title)
    db.session.add(new_conversation)
    db.session.commit()
    return new_conversation


def create_message(conversation_id, role, content):
    new_message = Message(conversation_id=conversation_id,
                          role=role, content=content)
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
    messages = Message.query.filter_by(
        conversation_id=conversation_id).order_by(Message.created_at).all()
    return messages


def get_conversation_messages_by_role(conversation_id, role):
    messages = Message.query.filter_by(
        conversation_id=conversation_id, role=role).order_by(Message.created_at).all()
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
