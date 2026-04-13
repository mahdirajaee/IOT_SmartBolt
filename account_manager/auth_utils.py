import jwt
import bcrypt
import hashlib
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self):
        self.secret_key = os.getenv('JWT_SECRET_KEY', 'default-secret-key')
        self.algorithm = os.getenv('JWT_ALGORITHM', 'HS256')
        self.expiry_hours = int(os.getenv('JWT_EXPIRY_HOURS', 24))
        self.bcrypt_rounds = int(os.getenv('BCRYPT_ROUNDS', 12))
    
    def hash_password(self, password):
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt(rounds=self.bcrypt_rounds)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, password, password_hash):
        password_bytes = password.encode('utf-8')
        hash_bytes = password_hash.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    
    def generate_token(self, user_id, username, role):
        expiry = datetime.utcnow() + timedelta(hours=self.expiry_hours)
        payload = {
            'user_id': user_id,
            'username': username,
            'role': role,
            'exp': expiry,
            'iat': datetime.utcnow()
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token, expiry
    
    def decode_token(self, token):
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {str(e)}")
    
    def hash_token(self, token):
        return hashlib.sha256(token.encode()).hexdigest()
    
    def validate_role(self, required_role, user_role):
        role_hierarchy = {
            'viewer': 0,
            'operator': 1,
            'admin': 2
        }
        
        required_level = role_hierarchy.get(required_role, 0)
        user_level = role_hierarchy.get(user_role, 0)
        
        return user_level >= required_level
    
    def extract_token_from_header(self, authorization_header):
        if not authorization_header:
            return None
        
        parts = authorization_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None
        
        return parts[1]