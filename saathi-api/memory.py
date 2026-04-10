"""
memory.py — Saathi Module 6: Conversational Memory & Gentle Nudge Engine
Handles episodic memory storage, narrative condensation, and nudge scheduling.
"""

import sqlite3
import uuid
import datetime
import json
import re


DB_FILE = "saathi.db"

# ── Topics for memory partitioning ───────────────────────────────────────────
TOPIC_KEYWORDS = {
    "research": ["paper", "thesis", "arxiv", "research", "methodology", "results", "deadline", "submit", "iccaiml", "dataset", "pipeline", "section", "chapter", "review", "conference"],
    "personal":  ["feel", "worried", "anxious", "stress", "excited", "happy", "sad", "tired", "relationship", "family", "friend", "khushi", "supervisor", "advisor"],
    "academic":  ["exam", "grade", "assignment", "lecture", "course", "study", "university", "semester", "project", "professor", "class"],
    "social":    ["meet", "event", "party", "call", "email", "message", "slack", "team", "colleague", "ping", "sync"],
}

# ── Worry-detection patterns ──────────────────────────────────────────────────
WORRY_PATTERNS = [
    r"\bworr(y|ied|ying)\b",
    r"\banxious\b", r"\bstressed\b", r"\bscared\b", r"\bfrustrat\w+\b",
    r"\bnot sure\b", r"\bdon'?t know\b", r"\bhaven'?t\b", r"\bfalling behind\b",
    r"\brunning out\b", r"\bno time\b", r"\bpanic\b",
]

# ── Time-trigger phrases → nudge after N days ─────────────────────────────────
TIME_TRIGGERS = [
    (r"\bthis week\b",  3),
    (r"\btoday\b",      1),
    (r"\btomorrow\b",   1),
    (r"\bnext week\b",  5),
    (r"\bsoon\b",       2),
    (r"\bshortly\b",    2),
    (r"\bin (\d+) days?\b", None),  # dynamic
]

def _detect_topic(text: str) -> str:
    text_l = text.lower()
    scores = {t: 0 for t in TOPIC_KEYWORDS}
    for topic, kws in TOPIC_KEYWORDS.items():
        for kw in kws:
            if kw in text_l:
                scores[topic] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"

def _detect_worry(text: str) -> bool:
    text_l = text.lower()
    return any(re.search(p, text_l) for p in WORRY_PATTERNS)

def _extract_nudge_delay(text: str) -> int | None:
    """Return number of days after which a nudge should fire, or None."""
    text_l = text.lower()
    # Dynamic: "in X days"
    m = re.search(r"in (\d+) days?", text_l)
    if m:
        return int(m.group(1))
    for pattern, days in TIME_TRIGGERS:
        if days is not None and re.search(pattern, text_l):
            return days
    return None

def _is_intent_bearing(text: str) -> bool:
    """Returns True if the message expresses an intent to do something."""
    intent_patterns = [
        r"\bneed to\b", r"\bwant to\b", r"\bgoing to\b", r"\bwill\b",
        r"\bplan(?:ning)? to\b", r"\bintend(ing)? to\b",
        r"\bshould\b", r"\bmust\b", r"\bhave to\b",
    ]
    text_l = text.lower()
    return any(re.search(p, text_l) for p in intent_patterns)


# ── DB helpers ────────────────────────────────────────────────────────────────

def init_memory_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Episodic memory entries (raw conversation moments)
    c.execute("""
        CREATE TABLE IF NOT EXISTS episodic_memory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            topic       TEXT NOT NULL DEFAULT 'general',
            source      TEXT NOT NULL DEFAULT 'conversation',
            content     TEXT NOT NULL,
            is_summary  INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Named facts ("Remember that Khushi is handling the NEAT pipeline")
    c.execute("""
        CREATE TABLE IF NOT EXISTS named_facts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT NOT NULL,
            key_phrase   TEXT NOT NULL,
            content     TEXT NOT NULL,
            topic       TEXT NOT NULL DEFAULT 'general',
            is_deleted  INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Nudge store
    c.execute("""
        CREATE TABLE IF NOT EXISTS nudges (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at      TEXT NOT NULL,
            fire_at         TEXT NOT NULL,
            topic           TEXT NOT NULL DEFAULT 'general',
            message         TEXT NOT NULL,
            context_snippet TEXT,
            nudge_type      TEXT NOT NULL DEFAULT 'time',
            status          TEXT NOT NULL DEFAULT 'pending',
            acknowledged    INTEGER NOT NULL DEFAULT 0,
            suppressed_forever INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Worry signals (for proactive help detection)
    c.execute("""
        CREATE TABLE IF NOT EXISTS worry_signals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            topic       TEXT NOT NULL,
            snippet     TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ── Episodic Memory ───────────────────────────────────────────────────────────

def store_episode(content: str, source: str = "conversation", is_summary: bool = False):
    """Store a single episodic memory entry."""
    topic = _detect_topic(content)
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO episodic_memory (timestamp, topic, source, content, is_summary) VALUES (?,?,?,?,?)",
        (now, topic, source, content, 1 if is_summary else 0)
    )
    conn.commit()
    conn.close()


def get_episodes(topic: str = None, limit: int = 20, since_days: int = None):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    clauses = []
    params = []
    if topic:
        clauses.append("topic = ?")
        params.append(topic)
    if since_days:
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=since_days)).isoformat()
        clauses.append("timestamp >= ?")
        params.append(cutoff)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    c.execute(f"SELECT * FROM episodic_memory {where} ORDER BY id DESC LIMIT ?", params + [limit])
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def search_episodes(query_text: str, limit: int = 5):
    """Simple keyword search across episodic memory."""
    terms = query_text.lower().split()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM episodic_memory ORDER BY id DESC LIMIT 200")
    all_rows = [dict(r) for r in c.fetchall()]
    conn.close()

    def score(row):
        text = row["content"].lower()
        return sum(1 for t in terms if t in text)

    scored = [(score(r), r) for r in all_rows if score(r) > 0]
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:limit]]


def condense_old_episodes(days_ago: int = 3):
    """Condense episodes older than N days into a summary entry."""
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days_ago)).isoformat()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT * FROM episodic_memory WHERE timestamp < ? AND is_summary = 0",
        (cutoff,)
    )
    old = [dict(r) for r in c.fetchall()]
    conn.close()

    if len(old) < 5:
        return  # not enough to condense

    by_topic = {}
    for ep in old:
        by_topic.setdefault(ep["topic"], []).append(ep["content"])

    for topic, contents in by_topic.items():
        summary = f"[Condensed memory — {topic}] " + " | ".join(contents[:8])
        store_episode(summary, source="condensed", is_summary=True)

    # Delete the originals
    ids = [ep["id"] for ep in old]
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(f"DELETE FROM episodic_memory WHERE id IN ({','.join('?' for _ in ids)})", ids)
    conn.commit()
    conn.close()


# ── Named Facts API ───────────────────────────────────────────────────────────

def store_named_fact(content: str, key_phrase: str = ""):
    topic = _detect_topic(content)
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO named_facts (created_at, key_phrase, content, topic) VALUES (?,?,?,?)",
        (now, key_phrase or content[:40], content, topic)
    )
    conn.commit()
    conn.close()


def delete_named_fact(query_text: str):
    """Mark facts matching the query as deleted."""
    terms = query_text.lower().split()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM named_facts WHERE is_deleted = 0")
    rows = [dict(r) for r in c.fetchall()]

    to_delete = []
    for row in rows:
        combined = (row["key_phrase"] + " " + row["content"]).lower()
        if any(t in combined for t in terms):
            to_delete.append(row["id"])

    if to_delete:
        c.execute(f"UPDATE named_facts SET is_deleted = 1 WHERE id IN ({','.join('?' for _ in to_delete)})", to_delete)
        conn.commit()
    conn.close()
    return len(to_delete)


def get_all_facts(topic: str = None):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if topic:
        c.execute("SELECT * FROM named_facts WHERE is_deleted = 0 AND topic = ? ORDER BY id DESC", (topic,))
    else:
        c.execute("SELECT * FROM named_facts WHERE is_deleted = 0 ORDER BY id DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ── Nudge Engine ──────────────────────────────────────────────────────────────

def maybe_create_nudge(user_message: str, context_snippet: str = ""):
    """Analyse a user message and optionally schedule a nudge."""
    if not _is_intent_bearing(user_message):
        return

    delay_days = _extract_nudge_delay(user_message)
    if delay_days is None:
        return

    topic = _detect_topic(user_message)
    fire_at = (datetime.datetime.now() + datetime.timedelta(days=delay_days)).isoformat()
    now = datetime.datetime.now().isoformat()

    # Build gentle nudge message
    snippet = user_message[:120]
    nudge_msg = f"You mentioned: \"{snippet}…\" — how is that going?"

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """INSERT INTO nudges (created_at, fire_at, topic, message, context_snippet, nudge_type, status)
           VALUES (?,?,?,?,?,?,?)""",
        (now, fire_at, topic, nudge_msg, context_snippet, "time", "pending")
    )
    conn.commit()
    conn.close()


def maybe_create_worry_nudge(user_message: str):
    """If the message expresses worry, store a worry signal and possibly schedule a nudge."""
    if not _detect_worry(user_message):
        return

    topic = _detect_topic(user_message)
    now = datetime.datetime.now().isoformat()

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Count recent worry signals for this topic
    recent_cutoff = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
    c.execute(
        "SELECT COUNT(*) FROM worry_signals WHERE topic = ? AND timestamp >= ?",
        (topic, recent_cutoff)
    )
    worry_count = c.fetchone()[0]

    c.execute(
        "INSERT INTO worry_signals (timestamp, topic, snippet) VALUES (?,?,?)",
        (now, topic, user_message[:200])
    )

    # If this is the 2nd+ worry signal about the same topic → proactive nudge
    if worry_count >= 1:
        fire_at = (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat()
        nudge_msg = f"I've noticed you've mentioned worries about {topic} a few times. Would you like to talk through it, or can I help you make a plan?"
        c.execute(
            """INSERT INTO nudges (created_at, fire_at, topic, message, context_snippet, nudge_type, status)
               VALUES (?,?,?,?,?,?,?)""",
            (now, fire_at, topic, nudge_msg, user_message[:120], "worry", "pending")
        )

    conn.commit()
    conn.close()


def get_pending_nudges(nudge_sensitivity: str = "balanced") -> list:
    """Return nudges that are due to fire, respecting sensitivity setting."""
    now_str = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT * FROM nudges
           WHERE status = 'pending'
             AND fire_at <= ?
             AND acknowledged = 0
             AND suppressed_forever = 0
           ORDER BY fire_at ASC""",
        (now_str,)
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    # Apply sensitivity filtering
    if nudge_sensitivity == "light":
        rows = [r for r in rows if r["nudge_type"] == "time"][:1]
    elif nudge_sensitivity == "balanced":
        rows = rows[:3]
    # "proactive" → return all

    return rows


def acknowledge_nudge(nudge_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE nudges SET acknowledged = 1, status = 'done' WHERE id = ?", (nudge_id,))
    conn.commit()
    conn.close()


def suppress_nudge_topic(topic_or_phrase: str):
    """Suppress all pending nudges for a topic permanently."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "UPDATE nudges SET suppressed_forever = 1 WHERE status = 'pending' AND (topic = ? OR message LIKE ?)",
        (topic_or_phrase, f"%{topic_or_phrase}%")
    )
    conn.commit()
    conn.close()


def get_all_nudges_history() -> list:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM nudges ORDER BY created_at DESC LIMIT 50")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ── Memory Command Parser ─────────────────────────────────────────────────────

class MemoryCommandResult:
    def __init__(self, handled: bool, reply: str = "", data: dict = None):
        self.handled = handled
        self.reply = reply
        self.data = data or {}


def parse_memory_command(text: str) -> MemoryCommandResult:
    """
    Detect and handle special memory commands in user input.
    Returns MemoryCommandResult(handled=True) if intercepted.
    """
    t = text.strip()
    t_l = t.lower()

    # ── REMEMBER ──────────────────────────────────────────────────────────────
    if t_l.startswith("remember that") or t_l.startswith("remember:"):
        content = re.sub(r"^remember\s*(that|:)?\s*", "", t, flags=re.IGNORECASE).strip()
        store_named_fact(content)
        store_episode(f"User asked me to remember: {content}")
        return MemoryCommandResult(True, f"✦ Noted and stored: "{content}"")

    # ── FORGET ────────────────────────────────────────────────────────────────
    if t_l.startswith("forget what i said about") or t_l.startswith("forget:"):
        query = re.sub(r"^forget(what i said about|:)?\s*", "", t, flags=re.IGNORECASE).strip()
        deleted = delete_named_fact(query)
        return MemoryCommandResult(True, f"✦ Cleared {deleted} memory entry(ies) related to "{query}".")

    # ── WHAT DO YOU REMEMBER ─────────────────────────────────────────────────
    m = re.match(r"what do you remember about (.+)", t_l)
    if m:
        topic_query = m.group(1).strip()
        episodes = search_episodes(topic_query, limit=5)
        facts = get_all_facts()
        relevant_facts = [f for f in facts if topic_query in f["content"].lower() or topic_query in f["key_phrase"].lower()]

        parts = []
        if relevant_facts:
            parts.append("**Named facts:**\n" + "\n".join(f"• {f['content']}" for f in relevant_facts))
        if episodes:
            parts.append("**Conversation memories:**\n" + "\n".join(f"• [{e['topic']}] {e['content'][:120]}" for e in episodes))
        if not parts:
            reply = f"I don't have specific memories about "{topic_query}" yet."
        else:
            reply = "\n\n".join(parts)
        return MemoryCommandResult(True, reply, {"facts": relevant_facts, "episodes": episodes})

    # ── WHAT DID WE TALK ABOUT LAST WEEK ─────────────────────────────────────
    if re.search(r"what did we (talk|discuss|say)\b", t_l):
        days = 7
        m2 = re.search(r"last (\d+) days?", t_l)
        if m2:
            days = int(m2.group(1))
        episodes = get_episodes(since_days=days, limit=10)
        if not episodes:
            reply = "I don't have memories from that period yet."
        else:
            lines = [f"• [{e['timestamp'][:10]} · {e['topic']}] {e['content'][:100]}" for e in episodes]
            reply = f"Here's what I remember from the last {days} days:\n\n" + "\n".join(lines)
        return MemoryCommandResult(True, reply, {"episodes": episodes})

    # ── NEVER REMIND ME ───────────────────────────────────────────────────────
    m3 = re.match(r"never remind me about (.+)", t_l)
    if m3:
        topic_phrase = m3.group(1).strip()
        suppress_nudge_topic(topic_phrase)
        return MemoryCommandResult(True, f"✦ I'll never nudge you about "{topic_phrase}" again.")

    return MemoryCommandResult(False)


# ── Context Retrieval for Chat ────────────────────────────────────────────────

def get_relevant_memory_context(user_message: str, max_chars: int = 600) -> str:
    """Build a memory context string to inject into the LLM prompt."""
    # Relevant episodes
    episodes = search_episodes(user_message, limit=4)
    facts = get_all_facts()

    # Filter facts that have keyword overlap
    terms = set(user_message.lower().split())
    relevant_facts = [
        f for f in facts
        if any(t in f["content"].lower() or t in f["key_phrase"].lower() for t in terms)
    ][:4]

    parts = []
    if relevant_facts:
        parts.append("Named facts: " + " | ".join(f["content"] for f in relevant_facts))
    if episodes:
        parts.append("Past memories: " + " | ".join(e["content"][:80] for e in episodes))

    context = "\n".join(parts)
    return context[:max_chars] if context else ""
