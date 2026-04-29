import cherrypy
import json
import os
import sys
import logging
from dotenv import load_dotenv
from db_manager import DatabaseManager
from auth_utils import AuthManager
from models import User

import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common_utils import CatalogClient
from internal_auth import resolve_internal_api_key

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AccountManagerWebService(object):
    exposed = True
    
    def __init__(self):
        self.db = DatabaseManager()
        self.auth = AuthManager()
        self.internal_api_key = resolve_internal_api_key("account_manager")
        self.init_default_admin()
        self.start_cleanup_thread()
    
    def init_default_admin(self):
        try:
            admin_username = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
            existing_admin = self.db.get_user_by_username(admin_username)
            
            if not existing_admin:
                admin_password = os.getenv('DEFAULT_ADMIN_PASSWORD', 'ict2022')
                admin_email = os.getenv('DEFAULT_ADMIN_EMAIL', 'admin@iot-system.local')
                password_hash = self.auth.hash_password(admin_password)
                
                user_id = self.db.create_user(
                    username=admin_username,
                    email=admin_email,
                    password_hash=password_hash,
                    role='admin'
                )
                logger.info(f"Default admin user created with ID: {user_id}")
                logger.warning("Default admin password should be changed in production")

        except Exception as e:
            logger.error(f"Failed to create default admin: {e}")
    
    def start_cleanup_thread(self):
        def cleanup_expired_sessions():
            while True:
                try:
                    expired = self.db.cleanup_expired_sessions()
                    if expired > 0:
                        logger.info(f"Cleaned up {expired} expired sessions")
                except Exception as e:
                    logger.error(f"Session cleanup error: {e}")
                time.sleep(3600)
        
        cleanup_thread = threading.Thread(target=cleanup_expired_sessions, daemon=True)
        cleanup_thread.start()
    
    def json_response(self, data, status=200):
        cherrypy.response.status = status
        return json.dumps(data).encode('utf-8')
    
    def get_current_user(self):
        auth_header = cherrypy.request.headers.get('Authorization')
        token = self.auth.extract_token_from_header(auth_header)
        
        if not token:
            return None
        
        try:
            payload = self.auth.decode_token(token)
            token_hash = self.auth.hash_token(token)
            session = self.db.get_valid_session(token_hash)
            
            if not session:
                return None
            
            user = self.db.get_user_by_id(payload['user_id'])
            return User.from_db_row(user) if user else None
        except Exception:
            return None
    
    def _to_dual_format(self, user_obj):
        d = user_obj.to_dict()
        sectors = [{"sectorID": d["sector_id"]}] if d.get("sector_id") else []
        d["userID"] = d["id"]
        d["userName"] = d["username"]
        d["chatID"] = d.get("telegram_chat_id")
        d["sectors"] = sectors
        return d

    def require_auth(self, required_role='viewer'):
        user = self.get_current_user()
        if not user:
            cherrypy.response.status = 401
            return None, self.json_response({"error": "Authentication required"}, 401)
        
        if not self.auth.validate_role(required_role, user.role):
            cherrypy.response.status = 403
            return None, self.json_response({"error": "Insufficient permissions"}, 403)
        
        return user, None

    def require_internal_auth(self):
        provided_key = cherrypy.request.headers.get('X-Internal-API-Key')
        if not provided_key or provided_key != self.internal_api_key:
            cherrypy.response.status = 401
            return False, self.json_response({"error": "Internal authentication required"}, 401)
        return True, None
    
    def GET(self, *path, **query):
        try:
            if not path:
                return self.json_response({
                    "service": "Account Manager",
                    "status": "active",
                    "endpoints": {
                        "auth": {
                            "POST /register": "Register new user (admin only)",
                            "POST /login": "Authenticate and get JWT token",
                            "POST /logout": "Invalidate current session",
                            "GET /validate": "Validate token and get user info"
                        },
                        "users": {
                            "GET /users": "List all users (admin only)",
                            "PUT /users/{id}": "Update user",
                            "DELETE /users/{id}": "Delete user (admin only)"
                        }
                    }
                })
            
            endpoint = path[0]

            if endpoint == "health":
                return self.json_response({"status": "healthy"})

            if endpoint == "internal":
                internal_ok, error = self.require_internal_auth()
                if not internal_ok:
                    return error

                if len(path) >= 2 and path[1] == "users":
                    if len(path) == 2:
                        users = self.db.get_all_users()
                        users_list = []
                        for row in users:
                            user_obj = User.from_db_row(row)
                            users_list.append(self._to_dual_format(user_obj))
                        return self.json_response({"users": users_list})
                    elif len(path) == 3:
                        lookup = path[2]
                        try:
                            user_row = self.db.get_user_by_id(int(lookup))
                        except ValueError:
                            user_row = self.db.get_user_by_username(lookup)
                        if not user_row:
                            return self.json_response({"error": "User not found"}, 404)
                        user_obj = User.from_db_row(user_row)
                        return self.json_response({"user": self._to_dual_format(user_obj)})

                elif len(path) >= 2 and path[1] == "chat-ids":
                    sector_id = query.get("sector_id")
                    if not sector_id:
                        return self.json_response({"error": "sector_id required"}, 400)
                    users = self.db.get_users_by_sector(sector_id)
                    seen = set()
                    chat_ids = []
                    for row in users:
                        cid = row["telegram_chat_id"]
                        if cid and cid not in seen:
                            seen.add(cid)
                            chat_ids.append(cid)
                    return self.json_response({"chat_ids": chat_ids})

                return self.json_response({"error": "Internal endpoint not found"}, 404)

            if endpoint == "validate":
                user = self.get_current_user()
                if not user:
                    return self.json_response({"valid": False, "error": "Invalid or expired token"}, 401)
                
                return self.json_response({
                    "valid": True,
                    "user": user.to_dict()
                })
            
            elif endpoint == "users":
                if len(path) != 1:
                    return self.json_response({"error": f"Endpoint '/users/{'/'.join(path[1:])}' not found"}, 404)

                user, error = self.require_auth('admin')
                if error:
                    return error

                users = self.db.get_all_users()
                users_list = []
                for row in users:
                    user_obj = User.from_db_row(row)
                    users_list.append(user_obj.to_dict())

                return self.json_response({"users": users_list})

            else:
                return self.json_response({"error": f"Endpoint '{endpoint}' not found"}, 404)
                
        except Exception as e:
            logger.error(f"GET error: {e}")
            return self.json_response({"error": str(e)}, 500)
    
    def POST(self, *path, **query):
        try:
            if not path:
                return self.json_response({"error": "Endpoint required"}, 400)
            
            endpoint = path[0]
            
            if endpoint == "register":
                current_user, error = self.require_auth('admin')
                if error:
                    return error
                
                input_data = json.loads(cherrypy.request.body.read())
                username = input_data.get('username')
                email = input_data.get('email')
                password = input_data.get('password')
                role = input_data.get('role', 'viewer')
                sector_id = input_data.get('sector_id')
                telegram_chat_id = input_data.get('telegram_chat_id')

                if not all([username, email, password]):
                    return self.json_response({"error": "Username, email, and password required"}, 400)

                new_user = User(username=username, email=email, role=role, sector_id=sector_id)
                validation_errors = new_user.validate()
                if validation_errors:
                    return self.json_response({"error": "Validation failed", "errors": validation_errors}, 400)

                if len(password) < 6:
                    return self.json_response({"error": "Password must be at least 6 characters"}, 400)

                try:
                    password_hash = self.auth.hash_password(password)
                    user_id = self.db.create_user(
                        username=username,
                        email=email,
                        password_hash=password_hash,
                        role=role,
                        sector_id=sector_id,
                        telegram_chat_id=telegram_chat_id
                    )

                    return self.json_response({
                        "message": "User created successfully",
                        "user_id": user_id
                    }, 201)
                except ValueError as e:
                    return self.json_response({"error": str(e)}, 409)
            
            elif endpoint == "login":
                input_data = json.loads(cherrypy.request.body.read())
                username = input_data.get('username')
                password = input_data.get('password')
                
                if not username or not password:
                    return self.json_response({"error": "Username and password required"}, 400)
                
                user = self.db.get_user_by_username(username)
                if not user:
                    return self.json_response({"error": "Invalid credentials"}, 401)
                
                if not self.auth.verify_password(password, user['password_hash']):
                    return self.json_response({"error": "Invalid credentials"}, 401)
                
                token, expires_at = self.auth.generate_token(
                    user['id'], 
                    user['username'], 
                    user['role']
                )
                
                token_hash = self.auth.hash_token(token)
                self.db.create_session(user['id'], token_hash, expires_at)
                
                user_obj = User.from_db_row(user)
                
                return self.json_response({
                    "message": "Login successful",
                    "token": token,
                    "expires_at": expires_at.isoformat(),
                    "user": user_obj.to_dict()
                })
            
            elif endpoint == "logout":
                auth_header = cherrypy.request.headers.get('Authorization')
                token = self.auth.extract_token_from_header(auth_header)
                
                if not token:
                    return self.json_response({"error": "No token provided"}, 400)
                
                token_hash = self.auth.hash_token(token)
                if self.db.invalidate_session(token_hash):
                    return self.json_response({"message": "Logout successful"})
                else:
                    return self.json_response({"error": "Session not found"}, 404)
            
            else:
                return self.json_response({"error": f"POST endpoint '{endpoint}' not found"}, 404)
                
        except Exception as e:
            logger.error(f"POST error: {e}")
            return self.json_response({"error": str(e)}, 500)
    
    def OPTIONS(self, *path, **query):
        # Handle preflight CORS requests
        cherrypy.response.headers['Access-Control-Allow-Origin'] = '*'
        cherrypy.response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        cherrypy.response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return ''
    
    def PUT(self, *path, **query):
        try:
            if not path:
                return self.json_response({"error": "Endpoint required"}, 400)
            
            endpoint = path[0]
            
            if endpoint == "internal":
                if len(path) >= 3 and path[1] == "users":
                    internal_ok, error = self.require_internal_auth()
                    if not internal_ok:
                        return error

                    user_id = int(path[2])
                    input_data = json.loads(cherrypy.request.body.read())
                    if "telegram_chat_id" in input_data or "chatID" in input_data:
                        chat_id = input_data["telegram_chat_id"] if "telegram_chat_id" in input_data else input_data["chatID"]
                        normalized_chat_id = None if chat_id in ("", None) else str(chat_id)
                        self.db.update_user(user_id, telegram_chat_id=normalized_chat_id)
                        return self.json_response({"message": "User updated"})
                    return self.json_response({"error": "No valid updates"}, 400)

            elif endpoint == "users":
                if len(path) < 2:
                    return self.json_response({"error": "User ID required"}, 400)

                user_id = int(path[1])
                current_user, error = self.require_auth('viewer')
                if error:
                    return error

                if current_user.role != 'admin' and current_user.id != user_id:
                    return self.json_response({"error": "Cannot update other users"}, 403)

                input_data = json.loads(cherrypy.request.body.read())
                updates = {}

                if 'email' in input_data:
                    updates['email'] = input_data['email']

                if 'password' in input_data:
                    if len(input_data['password']) < 6:
                        return self.json_response({"error": "Password must be at least 6 characters"}, 400)
                    updates['password_hash'] = self.auth.hash_password(input_data['password'])

                if current_user.role == 'admin':
                    if 'role' in input_data:
                        if input_data['role'] in ['admin', 'operator', 'viewer']:
                            updates['role'] = input_data['role']
                    if 'sector_id' in input_data:
                        updates['sector_id'] = input_data['sector_id']

                if 'telegram_chat_id' in input_data:
                    updates['telegram_chat_id'] = input_data['telegram_chat_id']

                if not updates:
                    return self.json_response({"error": "No valid updates provided"}, 400)

                if self.db.update_user(user_id, **updates):
                    return self.json_response({"message": "User updated successfully"})
                else:
                    return self.json_response({"error": "User not found"}, 404)
            
            else:
                return self.json_response({"error": f"PUT endpoint '{endpoint}' not found"}, 404)
                
        except Exception as e:
            logger.error(f"PUT error: {e}")
            return self.json_response({"error": str(e)}, 500)
    
    def DELETE(self, *path, **query):
        try:
            if not path:
                return self.json_response({"error": "Endpoint required"}, 400)
            
            endpoint = path[0]
            
            if endpoint == "users":
                if len(path) < 2:
                    return self.json_response({"error": "User ID required"}, 400)
                
                user_id = int(path[1])
                current_user, error = self.require_auth('admin')
                if error:
                    return error
                
                if current_user.id == user_id:
                    return self.json_response({"error": "Cannot delete yourself"}, 400)
                
                self.db.invalidate_user_sessions(user_id)

                if self.db.delete_user(user_id):
                    return self.json_response({"message": "User deleted successfully"})
                else:
                    return self.json_response({"error": "User not found"}, 404)
            
            else:
                return self.json_response({"error": f"DELETE endpoint '{endpoint}' not found"}, 404)
                
        except Exception as e:
            logger.error(f"DELETE error: {e}")
            return self.json_response({"error": str(e)}, 500)

def main():
    port = int(os.getenv("CHERRYPY_PORT", 8084))
    host = os.getenv("CHERRYPY_HOST", "0.0.0.0")
    
    cherrypy.config.update({
        'server.socket_host': host,
        'server.socket_port': port,
        'engine.autoreload.on': False
    })
    
    app_config = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [
                ('Content-Type', 'application/json'),
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            ]
        }
    }
    
    logger.info(f"Starting Account Manager Service on {host}:{port}")
    logger.info("Using SQLite database")

    # Register with Catalog
    catalog_url = os.getenv("CATALOG_URL", "http://localhost:8081")
    catalog_client = CatalogClient(catalog_url)
    catalog_client.register_service(
        name="account_manager",
        host=host,
        port=port,
        description="Authentication & authorization service"
    )

    cherrypy.quickstart(AccountManagerWebService(), '/', app_config)

if __name__ == "__main__":
    main()
