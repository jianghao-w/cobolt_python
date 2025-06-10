"""Chat history management utilities."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class ChatMessage:
    chat_id: str
    role: str
    content: str
    timestamp: datetime | None = None


@dataclass
class Chat:
    id: str
    title: str
    created_at: datetime | None = None


class ChatHistory:
    """In-memory chat history used during a conversation."""

    def __init__(self) -> None:
        self._messages: List[ChatMessage] = []

    def add(self, role: str, content: str) -> None:
        self._messages.append(ChatMessage("", role, content, datetime.utcnow()))

    def clear(self) -> None:
        self._messages.clear()

    def to_ollama(self) -> List[dict[str, str]]:
        return [
            {"role": msg.role, "content": msg.content} for msg in self._messages
        ]

    def __iter__(self) -> Iterable[ChatMessage]:
        return iter(self._messages)


class PersistentChatHistory:
    """SQLite backed chat history storage."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            app_data = Path.home() / ".cobolt"
            app_data.mkdir(parents=True, exist_ok=True)
            db_path = str(app_data / "chat_history.db")
        self.db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    role TEXT CHECK(role IN ('user','assistant','tool')) NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id ON chat_messages(chat_id)"
            )
            conn.commit()

    # ------------------------------------------------------------------
    def create_chat(self, chat_id: str, title: str = "New Chat") -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO chats (id, title) VALUES (?, ?)",
                (chat_id, title),
            )
            conn.commit()

    def get_chat(self, chat_id: str) -> Optional[Chat]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id, title, created_at FROM chats WHERE id=?", (chat_id,)
            ).fetchone()
            if not row:
                return None
            return Chat(id=row["id"], title=row["title"], created_at=row["created_at"])

    def update_chat_title(self, chat_id: str, title: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE chats SET title=? WHERE id=?",
                (title, chat_id),
            )
            conn.commit()

    def delete_chat(self, chat_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM chats WHERE id=?", (chat_id,))
            conn.commit()

    def get_recent_chats(self, limit: int = 20) -> List[Chat]:
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.title, c.created_at,
                       (SELECT content FROM chat_messages WHERE chat_id=c.id ORDER BY timestamp DESC LIMIT 1) as last_message
                FROM chats c
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            chats = [
                Chat(id=row["id"], title=row["title"], created_at=row["created_at"])
                for row in rows
            ]
            return chats

    def add_message(self, chat_id: str, role: str, content: str) -> None:
        if role not in {"user", "assistant", "tool"}:
            raise ValueError("Invalid role")
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO chat_messages (chat_id, role, content) VALUES (?, ?, ?)",
                (chat_id, role, content),
            )
            conn.commit()

    def get_messages(self, chat_id: str, limit: int = 100) -> List[ChatMessage]:
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT chat_id, role, content, timestamp
                FROM chat_messages
                WHERE chat_id=?
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()
            return [
                ChatMessage(
                    chat_id=row["chat_id"],
                    role=row["role"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                )
                for row in rows
            ]

    def clear_all(self) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM chat_messages")
            conn.execute("DELETE FROM chats")
            conn.commit()


# Singleton instance for convenience
persistent_chat_history = PersistentChatHistory()
