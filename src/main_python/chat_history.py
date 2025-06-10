# chat_history.py
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
import json
from pathlib import Path

class ChatHistory:
    def __init__(self, db_path: str = None):
        # Default to a local directory if no path is provided
        if db_path is None:
            app_data = os.path.join(str(Path.home()), ".cobolt")
            os.makedirs(app_data, exist_ok=True)
            db_path = os.path.join(app_data, "chat_history.db")
        
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        """Create and return a new database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Access columns by name
        return conn

    def _init_db(self):
        """Initialize the database with required tables"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create chats table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create chat_messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    role TEXT CHECK(role IN ('user', 'assistant', 'tool')) NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
                )
            ''')
            
            # Create index for faster lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id ON chat_messages(chat_id)')
            conn.commit()

    # Chat operations
    def create_chat(self, chat_id: str = None, title: str = "New Chat") -> str:
        """Create a new chat and return its ID"""
        if chat_id is None:
            import uuid
            chat_id = str(uuid.uuid4())
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chats (id, title) VALUES (?, ?)",
                (chat_id, title)
            )
            conn.commit()
        return chat_id

    def get_chat(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Get a chat by ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chats WHERE id = ?", (chat_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_recent_chats(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get a list of recent chats"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, 
                       (SELECT content FROM chat_messages 
                        WHERE chat_id = c.id 
                        ORDER BY timestamp DESC LIMIT 1) as last_message
                FROM chats c
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def update_chat_title(self, chat_id: str, title: str) -> bool:
        """Update a chat's title"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE chats SET title = ? WHERE id = ?",
                (title, chat_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat and all its messages"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
            conn.commit()
            return cursor.rowcount > 0

    # Message operations
    def add_message(self, chat_id: str, role: str, content: str) -> int:
        """Add a message to a chat"""
        # Input validation
        if not isinstance(chat_id, str) or not chat_id.strip():
            raise ValueError("Invalid chat_id")
        if role not in ['user', 'assistant', 'tool']:
            raise ValueError("Invalid role. Must be 'user', 'assistant', or 'tool'")
        if not isinstance(content, str):
            raise ValueError("Content must be a string")
            
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO chat_messages (chat_id, role, content) VALUES (?, ?, ?)",
                    (chat_id, role, content)
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Database error in add_message: {e}")
            raise

    def get_messages(self, chat_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get messages for a chat"""
        if not isinstance(chat_id, str) or not chat_id.strip():
            raise ValueError("Invalid chat_id")
            
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM chat_messages 
                    WHERE chat_id = ? 
                    ORDER BY timestamp ASC
                    LIMIT ?
                """, (chat_id, limit))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Database error in get_messages: {e}")
            return []

    def clear_all(self):
        """Clear all chats and messages"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM chat_messages")
                cursor.execute("DELETE FROM chats")
                conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in clear_all: {e}")
            raise

# Singleton instance
chat_history = ChatHistory()