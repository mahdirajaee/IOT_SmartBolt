import sqlite3
import os
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class UserRow:
    # wrapper class so we can use dict-like access
    # keeps compatibility with the rest of the code
    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key):
        return self._data.get(key)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()


class DatabaseManager:

    def __init__(self, db_path=None):
        default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.db')
        self.db_path = db_path or os.getenv('DB_PATH', default_path)
        self._init_tables()
        logger.info(f"Connected to SQLite database at {self.db_path}")

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Persistent in the DB header; survives recreating users.db.
        cursor.execute('PRAGMA journal_mode = WAL')

        # users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS iot_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'viewer',
                sector_id TEXT,
                telegram_chat_id TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            )
        ''')

        # sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS iot_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL,
                is_valid INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES iot_users(id)
            )
        ''')

        conn.commit()
        conn.close()

    def create_user(self, username, email, password_hash, role='viewer', sector_id=None, telegram_chat_id=None):
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO iot_users (username, email, password_hash, role, sector_id, telegram_chat_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, email, password_hash, role, sector_id, telegram_chat_id))

            conn.commit()
            user_id = cursor.lastrowid
            logger.info(f"Created user: {username}")
            conn.close()
            return user_id
        except sqlite3.IntegrityError as e:
            conn.close()
            error_msg = str(e)
            if 'username' in error_msg.lower():
                raise ValueError(f"Username '{username}' already exists")
            elif 'email' in error_msg.lower():
                raise ValueError(f"Email '{email}' already exists")
            raise

    def get_user_by_username(self, username):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM iot_users WHERE username = ? AND is_active = 1', (username,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return UserRow(dict(row))
        return None

    def get_user_by_id(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM iot_users WHERE id = ? AND is_active = 1', (user_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return UserRow(dict(row))
        return None

    def get_all_users(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, email, role, sector_id, created_at, is_active, telegram_chat_id
            FROM iot_users WHERE is_active = 1
        ''')
        rows = cursor.fetchall()
        conn.close()
        return [UserRow(dict(row)) for row in rows]

    def get_users_by_sector(self, sector_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, email, role, sector_id, created_at, is_active, telegram_chat_id
            FROM iot_users WHERE (sector_id = ? OR role = 'admin') AND is_active = 1
        ''', (sector_id,))
        rows = cursor.fetchall()
        conn.close()
        return [UserRow(dict(row)) for row in rows]

    def update_user(self, user_id, **kwargs):
        allowed_fields = ['email', 'role', 'sector_id', 'password_hash', 'telegram_chat_id']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates['updated_at'] = datetime.now(timezone.utc).isoformat()

        # build query dynamically
        set_clause = ', '.join([f'{k} = ?' for k in updates.keys()])
        values = list(updates.values()) + [user_id]

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            UPDATE iot_users SET {set_clause} WHERE id = ? AND is_active = 1
        ''', values)

        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def delete_user(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM iot_sessions WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM iot_users WHERE id = ?', (user_id,))

        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def create_session(self, user_id, token_hash, expires_at):
        expires_at_str = expires_at if isinstance(expires_at, str) else expires_at.isoformat()

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO iot_sessions (user_id, token_hash, expires_at)
            VALUES (?, ?, ?)
        ''', (user_id, token_hash, expires_at_str))

        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return session_id

    def get_valid_session(self, token_hash):
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM iot_sessions
            WHERE token_hash = ? AND is_valid = 1 AND expires_at > ?
        ''', (token_hash, now))
        row = cursor.fetchone()
        conn.close()

        if row:
            return UserRow(dict(row))
        return None

    def invalidate_session(self, token_hash):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE iot_sessions SET is_valid = 0 WHERE token_hash = ?', (token_hash,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def invalidate_user_sessions(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE iot_sessions SET is_valid = 0 WHERE user_id = ?', (user_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected

    def cleanup_expired_sessions(self):
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE iot_sessions SET is_valid = 0
            WHERE expires_at < ? AND is_valid = 1
        ''', (now,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected
