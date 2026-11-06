"""Conversation routes: a missing or foreign conversation is a 404, not a 500 (D1)."""

from datetime import UTC, datetime

import pytest

from app import db
from app.models import Conversation, Message


@pytest.fixture
def foreign_conversation(create_user):
    other = create_user(email="other@example.com", subscription_status="active")
    convo = Conversation(user_id=other.id, title="theirs")
    db.session.add(convo)
    db.session.commit()
    return convo


ROUTES = [
    ("get", "/conversation/{}/view"),
    ("get", "/conversation/{}/latest"),
    ("post", "/conversation/{}/edit"),
    ("post", "/conversation/{}/delete"),
]


@pytest.mark.parametrize("method, path", ROUTES)
def test_missing_conversation_is_404(client, subscriber, method, path):
    response = getattr(client, method)(path.format(999_999), data={"title": "x"})
    assert response.status_code == 404


@pytest.mark.parametrize("method, path", ROUTES)
def test_foreign_conversation_is_404(
    client, subscriber, foreign_conversation, method, path
):
    response = getattr(client, method)(
        path.format(foreign_conversation.id), data={"title": "x"}
    )
    assert response.status_code == 404
    assert db.session.get(Conversation, foreign_conversation.id).title == "theirs"


def test_latest_orders_same_second_rows_by_id(client, subscriber):
    convo = Conversation(user_id=subscriber.id, title="mine")
    db.session.add(convo)
    db.session.flush()
    stamp = datetime(2026, 11, 6, 12, 0, 0, tzinfo=UTC)
    for role in ("user", "assistant"):
        db.session.add(
            Message(
                conversation_id=convo.id,
                role=role,
                content=role,
                model="gpt-6.1-sol",
                created_at=stamp,
            )
        )
    db.session.commit()
    latest = client.get(f"/conversation/{convo.id}/latest").get_json()
    assert [m["role"] for m in latest] == ["user", "assistant"]


def test_chat_page_ignores_a_retired_model(client, subscriber):
    convo = Conversation(user_id=subscriber.id, title="old")
    db.session.add(convo)
    db.session.flush()
    db.session.add(
        Message(
            conversation_id=convo.id, role="user", content="x", model="gpt-3.5-turbo"
        )
    )
    db.session.commit()
    response = client.post("/chat", data={"conversation_id": convo.id})
    assert response.status_code == 200
    assert b'value="gpt-3.5-turbo"' not in response.data
