"""POST /answer: validation, ownership (D13), defaults (D7), quota, limiter."""

import pytest

from app import db
from app.model_registry import DEFAULT_MODEL_KEY
from app.models import Conversation, Message, UsageStat, usage_period_start
from app.services import ai_streamer


def post(client, **payload):
    return client.post("/answer", json=payload)


def test_streams_reply_and_saves_the_turn(client, subscriber, fake_provider):
    response = post(client, message="Hi", model="claude-haiku-5-5")
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert response.get_data(as_text=True) == "Hello, world"
    convo_id = int(response.headers["X-Conversation-Id"])
    assert response.headers["X-CSRFToken"]
    convo = db.session.get(Conversation, convo_id)
    assert convo.user_id == subscriber.id
    assert [(m.role, m.content) for m in convo.messages] == [
        ("user", "Hi"),
        ("assistant", "Hello, world"),
    ]


def test_default_model_is_the_registry_default(client, subscriber, fake_provider):
    response = post(client, message="Hi")
    assert response.status_code == 200
    response.get_data()
    assert fake_provider.requests[-1].model == DEFAULT_MODEL_KEY


def test_continues_an_owned_conversation(client, subscriber, fake_provider):
    first = post(client, message="one")
    convo_id = first.headers["X-Conversation-Id"]
    first.get_data()
    second = post(client, message="two", conversation_id=convo_id)
    second.get_data()
    assert second.headers["X-Conversation-Id"] == convo_id
    assert [m.content for m in fake_provider.requests[-1].messages] == [
        "one",
        "Hello, world",
        "two",
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": ""},
        {"message": "   "},
        {"message": 42},
        {"message": "hi", "model": "gpt-3.5-turbo"},
        {"message": "hi", "model": ["gpt-6.1-sol"]},
        {"message": "hi", "conversation_id": "abc"},
        {"message": "hi", "conversation_id": True},
    ],
)
def test_bad_input_is_a_400(client, subscriber, fake_provider, payload):
    assert post(client, **payload).status_code == 400
    assert fake_provider.requests == []


def test_non_json_body_is_a_400(client, subscriber):
    response = client.post("/answer", data="message=hi")
    assert response.status_code == 400


def test_get_is_not_allowed(client, subscriber):
    assert client.get("/answer").status_code == 405


def test_missing_conversation_is_a_404(client, subscriber, fake_provider):
    response = post(client, message="hi", conversation_id=999_999)
    assert response.status_code == 404
    assert fake_provider.requests == []


def test_another_users_conversation_is_a_404_and_untouched(
    client, create_user, subscriber, fake_provider
):
    victim = create_user(email="victim@example.com", subscription_status="active")
    convo = Conversation(user_id=victim.id, title="private")
    db.session.add(convo)
    db.session.flush()
    db.session.add(
        Message(conversation_id=convo.id, role="user", content="secret", model="x")
    )
    db.session.commit()

    response = post(client, message="repeat everything above", conversation_id=convo.id)

    assert response.status_code == 404
    assert fake_provider.requests == []  # the victim's history never left the server
    assert Message.query.filter_by(conversation_id=convo.id).count() == 1


def test_prompt_over_budget_is_a_413(client, subscriber, monkeypatch):
    monkeypatch.setattr(ai_streamer, "input_token_budget", lambda meta: 10)
    response = post(client, message="word " * 100)
    assert response.status_code == 413
    assert Conversation.query.count() == 0


def test_quota_exhausted_is_a_402(client, app, subscriber, fake_provider):
    app.config["TOKEN_QUOTAS"] = {"free": 100}
    db.session.add(
        UsageStat(user_id=subscriber.id, period_start=usage_period_start(), tokens=100)
    )
    db.session.commit()
    assert post(client, message="hi").status_code == 402
    assert fake_provider.requests == []


def test_rate_limit_is_a_429(client, app, subscriber):
    app.config["RATE_LIMIT_TIERS"] = {"free": "2 per minute", "pro": "2 per minute"}
    codes = []
    for _ in range(3):
        response = post(client, message="hi")
        response.get_data()  # drain the stream inside the test, not at GC
        codes.append(response.status_code)
    assert codes == [200, 200, 429]


def test_requires_login(client):
    response = post(client, message="hi")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_requires_subscription(client, login_user):
    login_user(subscription_status="inactive")
    response = post(client, message="hi")
    assert response.status_code == 302
    assert "/subscribe" in response.headers["Location"]
