from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from backend.app.repositories.conversations import ConversationRepository
from backend.app.repositories.messages import ConversationOwnershipError, MessageRepository
from backend.app.repositories.users import UserRepository


def create_user(db: Session, username: str, email: str):
    return UserRepository(db).create_user(
        username=username,
        email=email,
        password_hash=f"hash-{username}",
    )


def test_user_repository_create_and_get_by_email(db_session: Session):
    repo = UserRepository(db_session)

    user = repo.create_user("alice", "alice@example.com", "hash")

    assert repo.get_by_email("alice@example.com").id == user.id
    assert repo.get_by_username("alice").id == user.id
    assert repo.get_by_id(user.id).email == "alice@example.com"


def test_conversation_repository_enforces_user_ownership(db_session: Session):
    user_a = create_user(db_session, "alice", "alice@example.com")
    user_b = create_user(db_session, "bob", "bob@example.com")
    repo = ConversationRepository(db_session)
    conversation = repo.create_for_user(user_a.id, "Alice plan")

    assert repo.get_for_user(conversation.id, user_a.id) is not None
    assert repo.get_for_user(conversation.id, user_b.id) is None
    assert repo.list_for_user(user_b.id) == []


def test_message_repository_enforces_user_ownership(db_session: Session):
    user_a = create_user(db_session, "alice", "alice@example.com")
    user_b = create_user(db_session, "bob", "bob@example.com")
    conversation = ConversationRepository(db_session).create_for_user(user_a.id, "Alice plan")
    repo = MessageRepository(db_session)

    created = repo.create_message(
        user_id=user_a.id,
        conversation_id=conversation.id,
        role="user",
        content_json={"text": "hello"},
        content_text="hello",
    )

    assert created.sequence_no == 1
    assert len(repo.list_for_conversation(user_a.id, conversation.id)) == 1
    assert repo.list_for_conversation(user_b.id, conversation.id) == []


def test_message_repository_rejects_write_to_other_users_conversation(db_session: Session):
    user_a = create_user(db_session, "alice", "alice@example.com")
    user_b = create_user(db_session, "bob", "bob@example.com")
    conversation = ConversationRepository(db_session).create_for_user(user_a.id, "Alice plan")
    repo = MessageRepository(db_session)

    with pytest.raises(ConversationOwnershipError):
        repo.create_message(
            user_id=user_b.id,
            conversation_id=conversation.id,
            role="user",
            content_json={"text": "unauthorized"},
            content_text="unauthorized",
        )


def test_message_sequence_number_increments(db_session: Session):
    user = create_user(db_session, "alice", "alice@example.com")
    conversation = ConversationRepository(db_session).create_for_user(user.id, "Alice plan")
    repo = MessageRepository(db_session)

    first = repo.create_message(user.id, conversation.id, "user", {"text": "one"}, "one")
    second = repo.create_message(user.id, conversation.id, "assistant", {"text": "two"}, "two")

    assert first.sequence_no == 1
    assert second.sequence_no == 2
    assert repo.get_next_sequence_no(user.id, conversation.id) == 3
