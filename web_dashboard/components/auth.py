import requests
import os
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self):
        self.account_manager_url = os.getenv('ACCOUNT_MANAGER_URL', 'http://localhost:8084')

    def login(self, username: str, password: str) -> Dict:
        try:
            response = requests.post(
                f"{self.account_manager_url}/login",
                json={'username': username, 'password': password},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                if 'token' in data and 'user' in data:
                    return {
                        'success': True,
                        'token': data.get('token'),
                        'user': data.get('user'),
                        'expires_at': data.get('expires_at')
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Invalid response format from Account Manager'
                    }
            elif response.status_code == 401:
                return {
                    'success': False,
                    'error': 'Invalid username or password'
                }
            else:
                return {
                    'success': False,
                    'error': f'Authentication failed (Status: {response.status_code})'
                }

        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': 'Cannot connect to Account Manager service. Please ensure it is running on port 8084.'
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Account Manager service timeout. Please try again.'
            }
        except Exception as e:
            logger.error(f"Login error: {e}")
            return {
                'success': False,
                'error': f'Login failed: {str(e)}'
            }

    def verify_token(self, token: str) -> bool:
        try:
            headers = {'Authorization': f'Bearer {token}'}
            response = requests.get(
                f"{self.account_manager_url}/validate",
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return bool(data.get('valid', False))
            return False
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return False

