from datetime import datetime

class User:
    def __init__(self, user_id=None, username=None, email=None, role='viewer',
                 sector_id=None, created_at=None, is_active=True, telegram_chat_id=None):
        self.id = user_id
        self.username = username
        self.email = email
        self.role = role
        self.sector_id = sector_id
        self.created_at = created_at
        self.is_active = is_active
        self.telegram_chat_id = telegram_chat_id

    def to_dict(self, include_sensitive=False):
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'sector_id': self.sector_id,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'is_active': self.is_active,
            'telegram_chat_id': self.telegram_chat_id
        }
        return data
    
    @classmethod
    def from_db_row(cls, row):
        if row is None:
            return None
        return cls(
            user_id=row['id'],
            username=row['username'],
            email=row['email'],
            role=row['role'],
            sector_id=row['sector_id'],
            created_at=row['created_at'],
            is_active=row['is_active'],
            telegram_chat_id=row['telegram_chat_id'] if 'telegram_chat_id' in row.keys() else None
        )
    
    def validate(self):
        errors = []
        
        if not self.username or len(self.username) < 3:
            errors.append("Username must be at least 3 characters long")
        
        if not self.email or '@' not in self.email:
            errors.append("Invalid email address")
        
        if self.role not in ['admin', 'operator', 'viewer']:
            errors.append("Role must be 'admin', 'operator', or 'viewer'")
        
        return errors

class Session:
    def __init__(self, session_id=None, user_id=None, token_hash=None, 
                 created_at=None, expires_at=None, is_valid=True):
        self.id = session_id
        self.user_id = user_id
        self.token_hash = token_hash
        self.created_at = created_at
        self.expires_at = expires_at
        self.is_valid = is_valid
    
    @classmethod
    def from_db_row(cls, row):
        if row is None:
            return None
        return cls(
            session_id=row['id'],
            user_id=row['user_id'],
            token_hash=row['token_hash'],
            created_at=row['created_at'],
            expires_at=row['expires_at'],
            is_valid=row['is_valid']
        )