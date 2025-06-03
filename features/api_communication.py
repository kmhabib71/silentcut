import requests
import json
import os
import uuid
from typing import Optional, Dict, Any
import hashlib
import time

class SaaSAPIClient:
    """
    API client for communication between Python silence cutter app and SaaS website
    """
    
    def __init__(self):
        self.base_url = os.getenv('SAAS_API_URL', 'http://localhost:3000/api')
        self.session_id = self._generate_session_id()
        self.user_id = None
        self.user_email = None
        self.subscription_status = None
        
    def _generate_session_id(self) -> str:
        """Generate a unique session ID for this app instance"""
        machine_id = str(uuid.getnode())  # MAC address
        timestamp = str(int(time.time()))
        return hashlib.md5(f"{machine_id}_{timestamp}".encode()).hexdigest()
    
    def validate_file_usage(self, file_duration_minutes: float, user_identifier: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate if the user can process a file of given duration
        
        Args:
            file_duration_minutes: Duration of the file in minutes
            user_identifier: Email or user ID (optional for first-time users)
            
        Returns:
            Dictionary with validation result and user info
        """
        try:
            payload = {
                'sessionId': self.session_id,
                'fileDuration': file_duration_minutes,
                'userIdentifier': user_identifier
            }
            
            response = requests.post(
                f"{self.base_url}/validate-usage",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Update local user info
                if result.get('user'):
                    self.user_id = result['user'].get('id')
                    self.user_email = result['user'].get('email')
                    self.subscription_status = result['user'].get('subscription')
                
                return {
                    'allowed': result.get('allowed', False),
                    'message': result.get('message', ''),
                    'user': result.get('user'),
                    'requiresAuth': result.get('requiresAuth', False),
                    'remainingMinutes': result.get('remainingMinutes', 0),
                    'upgradeUrl': result.get('upgradeUrl', '')
                }
            else:
                return {
                    'allowed': False,
                    'message': 'Unable to validate usage. Please check your internet connection.',
                    'requiresAuth': False,
                    'error': True
                }
                
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return {
                'allowed': False,
                'message': 'Unable to connect to the service. Please check your internet connection.',
                'requiresAuth': False,
                'error': True
            }
    
    def record_usage(self, file_duration_minutes: float, file_name: str) -> bool:
        """
        Record the usage of a processed file
        
        Args:
            file_duration_minutes: Duration of the processed file
            file_name: Name of the processed file
            
        Returns:
            True if usage was recorded successfully
        """
        try:
            payload = {
                'sessionId': self.session_id,
                'fileDuration': file_duration_minutes,
                'fileName': file_name,
                'userId': self.user_id,
                'timestamp': int(time.time())
            }
            
            response = requests.post(
                f"{self.base_url}/record-usage",
                json=payload,
                timeout=10
            )
            
            return response.status_code == 200
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to record usage: {e}")
            return False
    
    def authenticate_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user with email and password
        
        Args:
            email: User's email
            password: User's password
            
        Returns:
            Authentication result
        """
        try:
            payload = {
                'email': email,
                'password': password,
                'sessionId': self.session_id
            }
            
            response = requests.post(
                f"{self.base_url}/auth/login",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.user_id = result['user']['id']
                    self.user_email = result['user']['email']
                    self.subscription_status = result['user']['subscription']
                
                return result
            else:
                return {
                    'success': False,
                    'message': 'Invalid credentials'
                }
                
        except requests.exceptions.RequestException as e:
            print(f"Authentication failed: {e}")
            return {
                'success': False,
                'message': 'Unable to connect to authentication service'
            }
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current user information
        
        Returns:
            User information if available
        """
        if not self.user_id:
            return None
            
        try:
            response = requests.get(
                f"{self.base_url}/user/{self.user_id}",
                params={'sessionId': self.session_id},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except requests.exceptions.RequestException:
            return None
    
    def open_auth_dialog(self) -> str:
        """
        Generate URL for authentication dialog
        
        Returns:
            URL to open for authentication
        """
        return f"{self.base_url.replace('/api', '')}/auth/signin?session={self.session_id}"
    
    def open_upgrade_page(self) -> str:
        """
        Generate URL for upgrade page
        
        Returns:
            URL to open for subscription upgrade
        """
        return f"{self.base_url.replace('/api', '')}/pricing?session={self.session_id}"
    
    def check_subscription_status(self) -> Optional[Dict[str, Any]]:
        """
        Check current subscription status
        
        Returns:
            Subscription information
        """
        if not self.user_id:
            return None
            
        try:
            response = requests.get(
                f"{self.base_url}/subscription/status",
                params={
                    'userId': self.user_id,
                    'sessionId': self.session_id
                },
                timeout=10
            )
            
            if response.status_code == 200:
                subscription_info = response.json()
                self.subscription_status = subscription_info
                return subscription_info
            else:
                return None
                
        except requests.exceptions.RequestException:
            return None

# Global instance for the application
api_client = SaaSAPIClient() 