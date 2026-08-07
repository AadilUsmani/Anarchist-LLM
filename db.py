"""
db.py - SQLite database module for GPT-1900 Chatbot
Handles all persistence: chats, messages, CRUD operations.
"""

import sqlite3
import os
from datetime import datetime

# Database file path
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_history.db")


def get_connection():
    """Get a SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database - create tables if they don't exist."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT 'New Chat',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
            CREATE INDEX IF NOT EXISTS idx_chats_updated ON chats(updated_at DESC);
        """)
        conn.commit()
    finally:
        conn.close()


# ─── Chat Operations ───

def create_chat(title: str = "New Chat") -> int:
    """Create a new chat and return its ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO chats (title, updated_at) VALUES (?, CURRENT_TIMESTAMP)",
            (title,)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_all_chats():
    """Get all chats ordered by most recently updated first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM chats ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_chat(chat_id: int):
    """Get a single chat by ID."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, title, created_at, updated_at FROM chats WHERE id = ?",
            (chat_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def rename_chat(chat_id: int, new_title: str) -> bool:
    """Rename a chat. Returns True if successful."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE chats SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_title, chat_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_chat(chat_id: int) -> bool:
    """Delete a chat and all its messages (CASCADE). Returns True if successful."""
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_chat_timestamp(chat_id: int):
    """Update the updated_at timestamp of a chat to now."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE chats SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (chat_id,)
        )
        conn.commit()
    finally:
        conn.close()


# ─── Message Operations ───

def add_message(chat_id: int, role: str, content: str) -> int:
    """Add a message to a chat. Returns the message ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, role, content)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_messages(chat_id: int):
    """Get all messages for a chat, ordered by creation time."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, role, content, created_at FROM messages WHERE chat_id = ? ORDER BY created_at ASC",
            (chat_id,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_message_count(chat_id: int) -> int:
    """Get the number of messages in a chat."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as count FROM messages WHERE chat_id = ?",
            (chat_id,)
        ).fetchone()
        return row["count"] if row else 0
    finally:
        conn.close()


# ─── Export ───

def generate_chat_markdown(chat_id: int) -> str:
    """Generate a markdown export of an entire chat conversation."""
    chat = get_chat(chat_id)
    if not chat:
        return ""

    messages = get_messages(chat_id)
    if not messages:
        return f"# {chat['title']}\n\n*No messages in this conversation.*\n"

    lines = [
        f"# {chat['title']}",
        "",
        f"**Created**: {chat['created_at']}",
        f"**Messages**: {len(messages)}",
        "",
        "---",
        "",
    ]

    for i, msg in enumerate(messages, 1):
        role_label = "**You**" if msg["role"] == "user" else "**GPT-1900**"
        timestamp = msg["created_at"]
        content = msg["content"]

        lines.append(f"### Message {i}")
        lines.append("")
        lines.append(f"{role_label} ({timestamp}):")
        lines.append("")
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def get_safe_filename(title: str) -> str:
    """Convert a chat title to a safe filename."""
    safe = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in title)
    safe = safe.strip().replace(' ', '_')
    date_str = datetime.now().strftime("%Y%m%d")
    return f"{safe}_{date_str}.md"


# Initialize database on module import
init_db()