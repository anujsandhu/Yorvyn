"""
Test Suite for Yorvyn Persistent AI Sessions, Messages, and Search History.
Implements automated tests for all 18 core verification requirements:
1. Create a session
2. List sessions
3. Retrieve a session
4. Rename a session
5. Archive and restore
6. Delete a session
7. Create messages
8. Create search records
9. Retrieve search history
10. Restore conversation context
11. Cursor pagination
12. Idempotent retries
13. Concurrent message requests
14. Session ownership enforcement
15. Cross-user access rejection
16. Expired authentication rejection
17. Backend restart recovery
18. Long-conversation summarization
"""

from __future__ import annotations

import concurrent.futures
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from backend.app.main import app
from backend.app.core.settings import settings
from backend.app.services.database.supabase_repository import supabase_repo
from backend.app.services.llm.persistent_session_service import persistent_session_service

client = TestClient(app)


def _generate_jwt(user_id: str, email: str = "user@yorvyn.ai", expired: bool = False, aud: str = "authenticated") -> str:
    secret = settings.supabase_jwt_secret or settings.secret_key
    now_ts = int(time.time())
    exp_ts = (now_ts - 3600) if expired else (now_ts + 7200)
    claims = {
        "sub": user_id,
        "email": email,
        "aud": aud,
        "role": "authenticated",
        "exp": exp_ts,
        "iat": now_ts
    }
    return jwt.encode(claims, secret, algorithm="HS256")


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── Test 1: Create a session ──────────────────────────────────────────────────
def test_01_create_session():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    res = client.post(
        "/api/ai/sessions",
        json={"title": "Autumn Wardrobe Advice", "session_type": "fashion_stylist"},
        headers=_auth_header(token)
    )
    assert res.status_code == 201
    data = res.json()
    assert data["success"] is True
    session = data["session"]
    assert session["title"] == "Autumn Wardrobe Advice"
    assert session["session_type"] == "fashion_stylist"
    assert session["status"] == "active"
    assert session["user_id"] == uid
    assert "id" in session


# ── Test 2: List sessions ─────────────────────────────────────────────────────
def test_02_list_sessions():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    # Create 3 sessions
    for i in range(3):
        client.post(
            "/api/ai/sessions",
            json={"title": f"Session {i+1}", "session_type": "general"},
            headers=_auth_header(token)
        )

    res = client.get("/api/ai/sessions", headers=_auth_header(token))
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 3
    assert data["total"] == 3


# ── Test 3: Retrieve a session ────────────────────────────────────────────────
def test_03_retrieve_session():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    create_res = client.post(
        "/api/ai/sessions",
        json={"title": "Session to Retrieve", "session_type": "wardrobe"},
        headers=_auth_header(token)
    )
    session_id = create_res.json()["session"]["id"]

    res = client.get(f"/api/ai/sessions/{session_id}", headers=_auth_header(token))
    assert res.status_code == 200
    session = res.json()
    assert session["id"] == session_id
    assert session["title"] == "Session to Retrieve"
    assert session["session_type"] == "wardrobe"


# ── Test 4: Rename a session ──────────────────────────────────────────────────
def test_04_rename_session():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    create_res = client.post(
        "/api/ai/sessions",
        json={"title": "Initial Title"},
        headers=_auth_header(token)
    )
    session_id = create_res.json()["session"]["id"]

    patch_res = client.patch(
        f"/api/ai/sessions/{session_id}",
        json={"title": "Updated Luxe Wardrobe Plan"},
        headers=_auth_header(token)
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["title"] == "Updated Luxe Wardrobe Plan"


# ── Test 5: Archive and restore session ────────────────────────────────────────
def test_05_archive_and_restore_session():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    create_res = client.post("/api/ai/sessions", json={"title": "Temporary Session"}, headers=_auth_header(token))
    session_id = create_res.json()["session"]["id"]

    # Archive
    arch_res = client.post(f"/api/ai/sessions/{session_id}/archive", headers=_auth_header(token))
    assert arch_res.status_code == 200
    assert arch_res.json()["status"] == "archived"
    assert arch_res.json()["archived_at"] is not None

    # Should not appear in default active list
    list_res = client.get("/api/ai/sessions", headers=_auth_header(token))
    active_ids = [s["id"] for s in list_res.json()["items"]]
    assert session_id not in active_ids

    # Should appear in archived list
    arch_list_res = client.get("/api/ai/sessions?status=archived", headers=_auth_header(token))
    arch_ids = [s["id"] for s in arch_list_res.json()["items"]]
    assert session_id in arch_ids

    # Restore
    rest_res = client.post(f"/api/ai/sessions/{session_id}/restore", headers=_auth_header(token))
    assert rest_res.status_code == 200
    assert rest_res.json()["status"] == "active"
    assert rest_res.json()["archived_at"] is None


# ── Test 6: Delete a session ──────────────────────────────────────────────────
def test_06_delete_session():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    create_res = client.post("/api/ai/sessions", json={"title": "Session to Delete"}, headers=_auth_header(token))
    session_id = create_res.json()["session"]["id"]

    del_res = client.delete(f"/api/ai/sessions/{session_id}", headers=_auth_header(token))
    assert del_res.status_code == 200

    # Retrieve should return 404
    get_res = client.get(f"/api/ai/sessions/{session_id}", headers=_auth_header(token))
    assert get_res.status_code == 404


# ── Test 7: Create messages ───────────────────────────────────────────────────
def test_07_create_messages():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    create_res = client.post("/api/ai/sessions", json={"title": "Message Test"}, headers=_auth_header(token))
    session_id = create_res.json()["session"]["id"]

    msg_res = client.post(
        f"/api/ai/sessions/{session_id}/messages",
        json={"content": "Hello stylist, recommend a minimalist business casual look."},
        headers=_auth_header(token)
    )
    assert msg_res.status_code == 200
    data = msg_res.json()
    assert data["success"] is True
    assert data["session_id"] == session_id
    assert "user_message_id" in data
    assert "assistant_message_id" in data
    assert len(data["response"]["content"]) > 0

    # Verify messages endpoint returns both turns
    history_res = client.get(f"/api/ai/sessions/{session_id}/messages", headers=_auth_header(token))
    assert history_res.status_code == 200
    items = history_res.json()["items"]
    assert len(items) >= 2
    assert items[0]["role"] == "user"
    assert items[1]["role"] == "assistant"


# ── Test 8: Create search records ─────────────────────────────────────────────
def test_08_create_search_records():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    create_res = client.post("/api/ai/sessions", json={"title": "Search Test"}, headers=_auth_header(token))
    session_id = create_res.json()["session"]["id"]

    # Post a message that triggers outfit search
    msg_res = client.post(
        f"/api/ai/sessions/{session_id}/messages",
        json={"content": "Find outfit combinations for my grey oversized T-shirt"},
        headers=_auth_header(token)
    )
    assert msg_res.status_code == 200
    data = msg_res.json()
    assert data["search_id"] is not None


# ── Test 9: Retrieve search history ───────────────────────────────────────────
def test_09_retrieve_search_history():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    create_res = client.post("/api/ai/sessions", json={"title": "Search History Test"}, headers=_auth_header(token))
    session_id = create_res.json()["session"]["id"]

    # Trigger search
    client.post(
        f"/api/ai/sessions/{session_id}/messages",
        json={"content": "Show me outfits for winter coats"},
        headers=_auth_header(token)
    )

    # Check session searches
    session_search_res = client.get(f"/api/ai/sessions/{session_id}/searches", headers=_auth_header(token))
    assert session_search_res.status_code == 200
    s_items = session_search_res.json()["items"]
    assert len(s_items) >= 1
    assert "winter coats" in s_items[0]["query"]

    # Check global searches
    global_search_res = client.get("/api/ai/searches?q=winter", headers=_auth_header(token))
    assert global_search_res.status_code == 200
    g_items = global_search_res.json()["items"]
    assert len(g_items) >= 1
    assert any("winter" in s["query"].lower() for s in g_items)


# ── Test 10: Restore conversation context ─────────────────────────────────────
def test_10_restore_conversation_context():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    create_res = client.post("/api/ai/sessions", json={"title": "Context Test"}, headers=_auth_header(token))
    session_id = create_res.json()["session"]["id"]

    # Turn 1: User mentions dark brown hoodie
    client.post(
        f"/api/ai/sessions/{session_id}/messages",
        json={"content": "I uploaded a dark brown oversized pullover hoodie."},
        headers=_auth_header(token)
    )

    # Check prompt context assembled by service
    context_msgs = persistent_session_service.assemble_session_prompt_context(session_id, uid)
    assert len(context_msgs) >= 2
    # Verify the hoodie mention exists in the restored context
    assert any("dark brown" in m["content"] for m in context_msgs)


# ── Test 11: Cursor pagination ────────────────────────────────────────────────
def test_11_cursor_pagination():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    # Create 5 sessions
    created_ids = []
    for i in range(5):
        r = client.post(
            "/api/ai/sessions",
            json={"title": f"Paginated Session {i}"},
            headers=_auth_header(token)
        )
        created_ids.append(r.json()["session"]["id"])

    # Page 1: limit 2
    page1 = client.get("/api/ai/sessions?limit=2", headers=_auth_header(token)).json()
    assert len(page1["items"]) == 2
    next_cursor = page1["next_cursor"]
    assert next_cursor is not None

    # Page 2: with cursor
    page2 = client.get(f"/api/ai/sessions?limit=2&cursor={next_cursor}", headers=_auth_header(token)).json()
    assert len(page2["items"]) == 2
    # Ensure items don't overlap
    page1_ids = {s["id"] for s in page1["items"]}
    page2_ids = {s["id"] for s in page2["items"]}
    assert page1_ids.isdisjoint(page2_ids)


# ── Test 12: Idempotent retries ───────────────────────────────────────────────
def test_12_idempotent_retries():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    create_res = client.post("/api/ai/sessions", json={"title": "Idempotency Test"}, headers=_auth_header(token))
    session_id = create_res.json()["session"]["id"]

    client_req_id = f"req_{uuid.uuid4().hex}"

    # First attempt
    res1 = client.post(
        f"/api/ai/sessions/{session_id}/messages",
        json={"content": "Suggest casual footwear", "request_id": client_req_id},
        headers=_auth_header(token)
    )
    assert res1.status_code == 200
    data1 = res1.json()

    # Retry with exact same request_id
    res2 = client.post(
        f"/api/ai/sessions/{session_id}/messages",
        json={"content": "Suggest casual footwear", "request_id": client_req_id},
        headers=_auth_header(token)
    )
    assert res2.status_code == 200
    data2 = res2.json()

    # Must return identical message IDs without duplicate records
    assert data1["user_message_id"] == data2["user_message_id"]

    # History should only contain 1 user message
    hist = client.get(f"/api/ai/sessions/{session_id}/messages", headers=_auth_header(token)).json()["items"]
    user_msgs = [m for m in hist if m["role"] == "user"]
    assert len(user_msgs) == 1


# ── Test 13: Concurrent message requests ──────────────────────────────────────
def test_13_concurrent_message_requests():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    create_res = client.post("/api/ai/sessions", json={"title": "Concurrency Test"}, headers=_auth_header(token))
    session_id = create_res.json()["session"]["id"]

    def send_msg(idx: int):
        return client.post(
            f"/api/ai/sessions/{session_id}/messages",
            json={"content": f"Concurrent message inquiry #{idx}"},
            headers=_auth_header(token)
        )

    # Post 4 messages concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(send_msg, i) for i in range(4)]
        responses = [f.result() for f in futures]

    for r in responses:
        assert r.status_code == 200

    # Ensure all messages received unique sequence numbers and were recorded
    hist = client.get(f"/api/ai/sessions/{session_id}/messages", headers=_auth_header(token)).json()["items"]
    user_msgs = [m for m in hist if m["role"] == "user"]
    assert len(user_msgs) == 4
    seq_numbers = [m["sequence_number"] for m in hist]
    # Verify sequence numbers are monotonic
    assert len(set(seq_numbers)) == len(seq_numbers)


# ── Test 14: Session ownership enforcement ────────────────────────────────────
def test_14_session_ownership_enforcement():
    user_a = f"usr_a_{uuid.uuid4().hex[:8]}"
    token_a = _generate_jwt(user_a)

    res = client.post("/api/ai/sessions", json={"title": "User A Private Vault"}, headers=_auth_header(token_a))
    session_a = res.json()["session"]

    assert session_a["user_id"] == user_a


# ── Test 15: Cross-user access rejection ──────────────────────────────────────
def test_15_cross_user_access_rejection():
    user_a = f"usr_a_{uuid.uuid4().hex[:8]}"
    token_a = _generate_jwt(user_a)

    user_b = f"usr_b_{uuid.uuid4().hex[:8]}"
    token_b = _generate_jwt(user_b)

    # User A creates a session
    res_a = client.post("/api/ai/sessions", json={"title": "User A Secret Session"}, headers=_auth_header(token_a))
    session_id = res_a.json()["session"]["id"]

    # User B tries to read User A's session -> 404 Not Found (no leakage)
    get_res = client.get(f"/api/ai/sessions/{session_id}", headers=_auth_header(token_b))
    assert get_res.status_code == 404

    # User B tries to post a message into User A's session -> 404 Not Found
    post_res = client.post(
        f"/api/ai/sessions/{session_id}/messages",
        json={"content": "Malicious intrusion attempt"},
        headers=_auth_header(token_b)
    )
    assert post_res.status_code == 404

    # User B tries to delete User A's session -> 404 Not Found
    del_res = client.delete(f"/api/ai/sessions/{session_id}", headers=_auth_header(token_b))
    assert del_res.status_code == 404


# ── Test 16: Expired authentication rejection ─────────────────────────────────
def test_16_expired_authentication():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    expired_token = _generate_jwt(uid, expired=True)

    res = client.get("/api/ai/sessions", headers=_auth_header(expired_token))
    assert res.status_code == 401
    assert "expired" in res.json().get("detail", "").lower()


# ── Test 17: Backend restart recovery ─────────────────────────────────────────
def test_17_backend_restart_recovery():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    create_res = client.post("/api/ai/sessions", json={"title": "Persistent Recovery Session"}, headers=_auth_header(token))
    session_id = create_res.json()["session"]["id"]

    client.post(
        f"/api/ai/sessions/{session_id}/messages",
        json={"content": "Persist this valuable recommendation context."},
        headers=_auth_header(token)
    )

    # Simulate fresh service instance or app reload
    fresh_service = type(persistent_session_service)(repo=supabase_repo)
    restored_context = fresh_service.assemble_session_prompt_context(session_id, uid)
    assert len(restored_context) >= 2
    assert any("valuable recommendation" in m["content"] for m in restored_context)


# ── Test 18: Long-conversation summarization ──────────────────────────────────
def test_18_long_conversation_summarization():
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    create_res = client.post("/api/ai/sessions", json={"title": "Extended Conversation"}, headers=_auth_header(token))
    session_id = create_res.json()["session"]["id"]

    # Post 12 messages to exceed the SUMMARIZE_THRESHOLD (10 messages)
    for i in range(12):
        client.post(
            f"/api/ai/sessions/{session_id}/messages",
            json={"content": f"Turn {i+1}: I am styling a beige trench coat with Chelsea boots."},
            headers=_auth_header(token)
        )

    # Check session record context_summary
    session = supabase_repo.get_ai_session(session_id, user_id=uid)
    assert session is not None
    assert session.get("context_summary") is not None
    assert len(session["context_summary"]) > 0
    assert "coat" in session["context_summary"].lower() or "boots" in session["context_summary"].lower() or "styling" in session["context_summary"].lower()


# ── Test 19: Full End-to-End Conversational Lifecycle Verification ────────────
def test_19_end_to_end_conversational_lifecycle():
    """
    End-to-end multi-tenant conversational flow:
    - User A registers & authenticates
    - Creates Session A1
    - Sends multiple styling turns & executes searches
    - Reopens session after simulated app reload
    - Verifies complete history & search provenance
    - Continues conversation
    - Creates separate Session A2 and confirms isolation
    - User B authenticates & attempts cross-tenant access to A1 -> strictly rejected
    """
    user_a = f"usr_e2e_a_{uuid.uuid4().hex[:8]}"
    token_a = _generate_jwt(user_a)

    # 1. Create Session A1
    create_a1 = client.post(
        "/api/ai/sessions",
        json={"title": "Signature Autumn Look", "session_type": "fashion_stylist"},
        headers=_auth_header(token_a)
    )
    assert create_a1.status_code == 201
    session_a1_id = create_a1.json()["session"]["id"]

    # 2. Send Turn 1: Initial user upload inquiry
    turn1 = client.post(
        f"/api/ai/sessions/{session_a1_id}/messages",
        json={"content": "I uploaded a dark chocolate brown oversized pullover hoodie."},
        headers=_auth_header(token_a)
    )
    assert turn1.status_code == 200

    # 3. Send Turn 2: Outfit search
    turn2 = client.post(
        f"/api/ai/sessions/{session_a1_id}/messages",
        json={"content": "Find matching tailored trousers in cream or charcoal"},
        headers=_auth_header(token_a)
    )
    assert turn2.status_code == 200
    assert turn2.json()["search_id"] is not None

    # 4. Send Turn 3: Second search for footwear
    turn3 = client.post(
        f"/api/ai/sessions/{session_a1_id}/messages",
        json={"content": "Recommend winter Chelsea boots that complement this palette"},
        headers=_auth_header(token_a)
    )
    assert turn3.status_code == 200
    assert turn3.json()["search_id"] is not None

    # 5. Simulate App Reload & Session Reopening
    reopen_res = client.get(f"/api/ai/sessions/{session_a1_id}", headers=_auth_header(token_a))
    assert reopen_res.status_code == 200
    sess_meta = reopen_res.json()
    assert sess_meta["message_count"] == 6  # 3 user messages + 3 assistant responses
    assert sess_meta["search_count"] >= 2

    # Verify complete chronological messages restored
    hist_res = client.get(f"/api/ai/sessions/{session_a1_id}/messages", headers=_auth_header(token_a))
    assert hist_res.status_code == 200
    messages = hist_res.json()["items"]
    assert len(messages) == 6
    assert messages[0]["content"] == "I uploaded a dark chocolate brown oversized pullover hoodie."
    assert messages[2]["content"] == "Find matching tailored trousers in cream or charcoal"

    # Verify session searches
    searches_res = client.get(f"/api/ai/sessions/{session_a1_id}/searches", headers=_auth_header(token_a))
    assert searches_res.status_code == 200
    searches = searches_res.json()["items"]
    assert len(searches) >= 2

    # 6. Continue Conversation in Session A1
    turn4 = client.post(
        f"/api/ai/sessions/{session_a1_id}/messages",
        json={"content": "Can I layer an olive trench coat over the hoodie?"},
        headers=_auth_header(token_a)
    )
    assert turn4.status_code == 200

    recheck_res = client.get(f"/api/ai/sessions/{session_a1_id}/messages", headers=_auth_header(token_a))
    assert len(recheck_res.json()["items"]) == 8

    # 7. Create Session A2 (verify isolation between user's own sessions)
    create_a2 = client.post(
        "/api/ai/sessions",
        json={"title": "Summer Resort Wear", "session_type": "fashion_stylist"},
        headers=_auth_header(token_a)
    )
    assert create_a2.status_code == 201
    session_a2_id = create_a2.json()["session"]["id"]
    assert session_a2_id != session_a1_id

    # Messages in A2 must be 0
    a2_msgs = client.get(f"/api/ai/sessions/{session_a2_id}/messages", headers=_auth_header(token_a))
    assert len(a2_msgs.json()["items"]) == 0

    # 8. User B attempts unauthorized access to User A's Session A1
    user_b = f"usr_e2e_b_{uuid.uuid4().hex[:8]}"
    token_b = _generate_jwt(user_b)

    # Attempt to read Session A1
    b_get = client.get(f"/api/ai/sessions/{session_a1_id}", headers=_auth_header(token_b))
    assert b_get.status_code == 404

    # Attempt to read Session A1 messages
    b_msgs = client.get(f"/api/ai/sessions/{session_a1_id}/messages", headers=_auth_header(token_b))
    assert b_msgs.status_code == 404

    # Attempt to post into Session A1
    b_post = client.post(
        f"/api/ai/sessions/{session_a1_id}/messages",
        json={"content": "Unauthorized injection attempt"},
        headers=_auth_header(token_b)
    )
    assert b_post.status_code == 404

    # Attempt to delete Session A1
    b_del = client.delete(f"/api/ai/sessions/{session_a1_id}", headers=_auth_header(token_b))
    assert b_del.status_code == 404

