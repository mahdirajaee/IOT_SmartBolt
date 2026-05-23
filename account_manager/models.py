import os
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

    def to_dict(self):
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
        username_min = int(os.environ['USERNAME_MIN_LENGTH'])

        if not self.username or len(self.username) < username_min:
            errors.append(f"Username must be at least {username_min} characters long")
        
        if not self.email or '@' not in self.email:
            errors.append("Invalid email address")
        
        if self.role not in ['admin', 'operator', 'viewer']:
            errors.append("Role must be 'admin', 'operator', or 'viewer'")
        
        return errors