import requests
import logging, time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)
# cache users to avoid hammering the auth service

class UserRole(Enum):
    ADMIN = 'admin'
    OPERATOR = 'operator'
    VIEWER = 'viewer'

@dataclass
class User:
    id: str
    username: str
    email: str
    role: UserRole
    sectors: list
    telegram_id: Optional[str] = None
    token: Optional[str] = None
    token_expiry: Optional[float] = None

class AuthClient:
    def __init__(self, account_manager_url='http://localhost:8084', catalog_url='http://localhost:8081'):
        self.account_manager_url = account_manager_url
        self.catalog_url = catalog_url
        self.session_cache = {}
        self.cache_ttl = 300  # 5 mins, increase if auth service is slow
        self.pipeline_sector_cache = {}
        self.pipeline_sector_cache_ttl = 300

    def _fetch_catalog_sectors(self, user_id):
        try:
            response = requests.get(
                f'{self.catalog_url}/users/{user_id}',
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                sectors = data.get('user', {}).get('sectors', [])
                return [s.get('sectorID') for s in sectors if s.get('sectorID')]
        except Exception as e:
            logger.warning(f'Failed to fetch catalog sectors for user {user_id}: {e}')
        return None
        
    def authenticate_user(self, username, password):
        try:
            response = requests.post(
                f'{self.account_manager_url}/login',
                json={'username': username, 'password': password},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()

                sector_id = data['user'].get('sector_id')
                sectors = [sector_id] if sector_id else []

                user = User(
                    id=data['user']['id'],
                    username=data['user']['username'],
                    email=data['user']['email'],
                    role=UserRole(data['user']['role']),
                    sectors=sectors,
                    token=data['token'],
                    token_expiry=time.time() + (24 * 3600)
                )

                catalog_sectors = self._fetch_catalog_sectors(user.id)
                if catalog_sectors:
                    user.sectors = catalog_sectors

                self.session_cache[username] = {
                    'user': user,
                    'cached_at': time.time()
                }

                logger.info(f'User {username} authenticated successfully')
                return user
            else:
                logger.warning(f'Authentication failed for {username}: {response.status_code}')
                return None

        except Exception as e:
            logger.error(f'Error authenticating user {username}: {e}')
            return None
    
    def validate_token(self, token):
        try:
            response = requests.get(
                f'{self.account_manager_url}/validate',
                headers={'Authorization': f'Bearer {token}'},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                sector_id = data['user'].get('sector_id')
                sectors = [sector_id] if sector_id else []

                user = User(
                    id=data['user']['id'],
                    username=data['user']['username'],
                    email=data['user']['email'],
                    role=UserRole(data['user']['role']),
                    sectors=sectors,
                    token=token
                )

                catalog_sectors = self._fetch_catalog_sectors(user.id)
                if catalog_sectors:
                    user.sectors = catalog_sectors

                logger.debug(f'Token validated for user {user.username}')
                return user

            logger.warning(f'Token validation failed: {response.status_code}')
            return None

        except Exception as e:
            logger.debug(f'Token validation error: {e}')
            return None
    
    def register_telegram_user(self, username, password, telegram_id):
        user = self.authenticate_user(username, password)
        if not user:
            return None

        try:
            response = requests.put(
                f'{self.account_manager_url}/users/{user.id}',
                headers={'Authorization': f'Bearer {user.token}'},
                json={'telegram_chat_id': telegram_id},
                timeout=5
            )

            if response.status_code == 200:
                user.telegram_id = telegram_id
                logger.info(f'Telegram ID registered for user {username}')
            else:
                logger.warning(f'Failed to register Telegram ID: {response.status_code}')

        except Exception as e:
            logger.error(f'Error registering Telegram ID: {e}')

        return user
    
    def get_user_by_telegram_id(self, telegram_id):
        # linear search through cache, not great but works for now
        for cache_entry in self.session_cache.values():
            user = cache_entry['user']
            if user.telegram_id == telegram_id:
                if time.time() - cache_entry['cached_at'] < self.cache_ttl:
                    return user
        return None
    
    def check_permission(self, user, action):
        # admin can do everything, skip other checks
        if user.role == UserRole.ADMIN:
            return True

        permissions = {
            UserRole.ADMIN: ['view', 'control', 'configure', 'emergency'],
            UserRole.OPERATOR: ['view', 'control', 'emergency'],
            UserRole.VIEWER: ['view']
        }

        user_perms = permissions.get(user.role, [])

        # this mapping is kinda hacky but works
        action_map = {
            'valve_control': 'control',
            'view_stats': 'view',
            'emergency_shutdown': 'emergency',
            'configure': 'configure'
        }
        required = action_map.get(action)
        return required in user_perms if required else False
    
    def _get_pipeline_sector(self, pipeline_id):
        if not pipeline_id:
            return None
        cached = self.pipeline_sector_cache.get(pipeline_id)
        if cached and time.time() - cached['cached_at'] < self.pipeline_sector_cache_ttl:
            return cached['sector_id']
        try:
            response = requests.get(
                f'{self.catalog_url}/pipelines/{pipeline_id}',
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                sector_id = data.get('pipeline', {}).get('sector_id')
                if sector_id:
                    self.pipeline_sector_cache[pipeline_id] = {
                        'sector_id': sector_id,
                        'cached_at': time.time()
                    }
                return sector_id
        except Exception as e:
            logger.warning(f'Failed to fetch sector for pipeline {pipeline_id}: {e}')
        return None

    def check_sector_access(self, user, pipeline_id):
        if user.role == UserRole.ADMIN:
            return True

        if not user.sectors:
            logger.warning(f"User {user.username} has no sectors assigned; denying access to {pipeline_id}")
            return False

        pipeline_sector = self._get_pipeline_sector(pipeline_id)
        if pipeline_sector is None:
            logger.warning(f"Could not resolve sector for pipeline {pipeline_id}; denying access")
            return False

        return pipeline_sector in user.sectors
    
    def logout_user(self, username):
        if username not in self.session_cache:
            return False

        user = self.session_cache[username]['user']
        try:
            response = requests.post(
                f'{self.account_manager_url}/logout',
                headers={'Authorization': f'Bearer {user.token}'},
                timeout=5
            )
            del self.session_cache[username]
            logger.info(f'User {username} logged out')
            return response.status_code == 200
        except Exception as e:
            logger.debug(f'Logout error: {e}')
            return False
    
    def refresh_token(self, user):
        # not really a refresh, just revalidate
        try:
            response = requests.get(
                f'{self.account_manager_url}/validate',
                headers={'Authorization': f'Bearer {user.token}'},
                timeout=5
            )

            if response.status_code == 200:
                user.token_expiry = time.time() + (24 * 3600)
                logger.info(f'Token refreshed for user {user.username}')
                return user.token
            else:
                logger.warning(f'Token refresh failed: {response.status_code}')
                return None

        except Exception as e:
            logger.error(f'Error refreshing token: {e}')
            return None
    
    def get_all_users(self, admin_token):
        
        try:
            response = requests.get(
                f'{self.account_manager_url}/users',
                headers={'Authorization': f'Bearer {admin_token}'},
                timeout=5
            )

            if response.status_code == 200:
                return response.json().get('users', [])
            logger.warning(f'Failed to get users: {response.status_code}')
            return None

        except Exception as e:
            logger.debug(f'Get users error: {e}')
            return None

    def clear_cache(self):
        self.session_cache.clear()
        logger.info('cache cleared')