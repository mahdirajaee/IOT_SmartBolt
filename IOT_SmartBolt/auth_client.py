import requests
import os
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class AuthClient:
    # auth client - validates tokens with account manager
    def __init__(self):
        self.account_manager_url = os.getenv('ACCOUNT_MANAGER_URL', 'http://localhost:8084')
        self.timeout = 5
        logger.info(f"AuthClient initialized with Account Manager URL: {self.account_manager_url}")

    def validate_token(self, token: str) -> Optional[Dict]:
        try:
            headers = {'Authorization': f'Bearer {token}'}
            response = requests.get(
                f"{self.account_manager_url}/validate",
                headers=headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('valid'):
                    user = data.get('user')
                    logger.debug(f"Token validated for user: {user.get('username')}")
                    return user
                else:
                    logger.warning(f"Invalid token: {data.get('error', 'Unknown error')}")
                    return None
            else:
                logger.warning(f"Token validation failed with status {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Timeout validating token with Account Manager")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to Account Manager at {self.account_manager_url}")
            return None
        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return None

    def check_permission(self, user: Dict, action: str) -> bool:
        role = user.get('role', 'viewer')

        # role permissions - check with team if these are right
        # TO DO: add more roles later?
        role_permissions = {
            'admin': ['view', 'control', 'emergency', 'configure'],
            'operator': ['view', 'control', 'emergency'],
            'viewer': ['view']
        }

        action_mapping = {
            'view_status': 'view',
            'view_rules': 'view',
            'view_stats': 'view',
            'view_history': 'view',
            'make_decision': 'control',
            'process_pipeline': 'control',
            'manual_control': 'control',
            'emergency_mode': 'emergency',
            'modify_monitoring': 'configure',
            'clear_cache': 'configure'
        }

        required_permission = action_mapping.get(action, 'view')
        user_permissions = role_permissions.get(role, [])

        has_permission = required_permission in user_permissions

        if not has_permission:
            logger.warning(
                f"Permission denied: User '{user.get('username')}' ({role}) "
                f"attempted action '{action}' (requires '{required_permission}')"
            )

        return has_permission

    def extract_token_from_header(self, authorization_header: str) -> Optional[str]:
        if not authorization_header:
            return None

        parts = authorization_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            logger.warning(f"Invalid Authorization header format")
            return None

        return parts[1]
