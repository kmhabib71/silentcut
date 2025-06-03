import requests
import json
import os
import uuid
from typing import Optional, Dict, Any, List
import hashlib
import time
import sqlite3
from pathlib import Path

class OfflineUsageTracker:
    """
    Local storage for tracking usage when offline or for anonymous users
    """
    
    def __init__(self):
        self.db_path = Path.home() / ".silence_cutter" / "usage.db"
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize local SQLite database for usage tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables with IF NOT EXISTS to avoid errors
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS device_info (
                id INTEGER PRIMARY KEY,
                permanent_id TEXT UNIQUE NOT NULL,
                machine_id TEXT,
                created_date TEXT,
                last_used_date TEXT,
                linked_email TEXT,
                device_name TEXT,
                registered_online BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # Check if registered_online column exists, add it if not (migration)
        cursor.execute("PRAGMA table_info(device_info)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'registered_online' not in columns:
            cursor.execute('ALTER TABLE device_info ADD COLUMN registered_online BOOLEAN DEFAULT FALSE')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_sessions (
                session_id TEXT PRIMARY KEY,
                permanent_id TEXT,
                total_minutes_used REAL DEFAULT 0,
                files_processed INTEGER DEFAULT 0,
                first_use_date TEXT,
                last_use_date TEXT,
                user_email TEXT,
                user_id TEXT,
                synced_to_server BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (permanent_id) REFERENCES device_info (permanent_id)
            )
        ''')
        
        # Check if permanent_id column exists in usage_sessions, add it if not (migration)
        cursor.execute("PRAGMA table_info(usage_sessions)")
        session_columns = [column[1] for column in cursor.fetchall()]
        if 'permanent_id' not in session_columns:
            cursor.execute('ALTER TABLE usage_sessions ADD COLUMN permanent_id TEXT')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                permanent_id TEXT,
                file_name TEXT,
                duration_minutes REAL,
                processed_date TEXT,
                synced_to_server BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (session_id) REFERENCES usage_sessions (session_id),
                FOREIGN KEY (permanent_id) REFERENCES device_info (permanent_id)
            )
        ''')
        
        # Check if permanent_id column exists in processed_files, add it if not (migration)
        cursor.execute("PRAGMA table_info(processed_files)")
        files_columns = [column[1] for column in cursor.fetchall()]
        if 'permanent_id' not in files_columns:
            cursor.execute('ALTER TABLE processed_files ADD COLUMN permanent_id TEXT')
        
        conn.commit()
        conn.close()
    
    def get_or_create_permanent_id(self) -> str:
        """Get or create a permanent device identifier"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if we already have a permanent ID (handle missing column gracefully)
        try:
            cursor.execute('SELECT permanent_id, registered_online FROM device_info LIMIT 1')
            result = cursor.fetchone()
        except sqlite3.OperationalError:
            # Column doesn't exist, use old query
            cursor.execute('SELECT permanent_id FROM device_info LIMIT 1')
            result = cursor.fetchone()
            if result:
                result = (result[0], False)  # Add default registered_online value
        
        if result:
            permanent_id = result[0]
            registered_online = result[1] if len(result) > 1 else False
            # Update last used date
            cursor.execute('''
                UPDATE device_info 
                SET last_used_date = ? 
                WHERE permanent_id = ?
            ''', (time.strftime('%Y-%m-%d %H:%M:%S'), permanent_id))
            
            conn.commit()
            conn.close()
            return permanent_id
        else:
            # Create new permanent ID based on machine characteristics
            machine_id = str(uuid.getnode())  # MAC address
            device_name = os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', 'Unknown'))
            
            # Create a permanent ID that's consistent for this machine
            permanent_id = hashlib.sha256(f"{machine_id}_{device_name}".encode()).hexdigest()[:16]
            
            cursor.execute('''
                INSERT INTO device_info 
                (permanent_id, machine_id, created_date, last_used_date, device_name, registered_online)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                permanent_id, 
                machine_id, 
                time.strftime('%Y-%m-%d %H:%M:%S'),
                time.strftime('%Y-%m-%d %H:%M:%S'),
                device_name,
                False
            ))
            
            conn.commit()
            conn.close()
            return permanent_id

    def mark_device_registered_online(self, permanent_id: str):
        """Mark device as successfully registered online"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE device_info 
            SET registered_online = TRUE
            WHERE permanent_id = ?
        ''', (permanent_id,))
        
        conn.commit()
        conn.close()

    def is_device_registered_online(self, permanent_id: str) -> bool:
        """Check if device is already registered online"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT registered_online FROM device_info WHERE permanent_id = ?', (permanent_id,))
            result = cursor.fetchone()
        except sqlite3.OperationalError:
            # Column doesn't exist, return False
            conn.close()
            return False
        
        conn.close()
        return result[0] if result else False
    
    def link_email_to_device(self, email: str):
        """Link user email to permanent device ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE device_info 
            SET linked_email = ?
        ''', (email,))
        
        # Also update all existing sessions
        cursor.execute('''
            UPDATE usage_sessions 
            SET user_email = ?
            WHERE permanent_id = (SELECT permanent_id FROM device_info LIMIT 1)
        ''', (email,))
        
        conn.commit()
        conn.close()
    
    def get_device_info(self) -> Dict[str, Any]:
        """Get device information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM device_info LIMIT 1')
            result = cursor.fetchone()
        except sqlite3.OperationalError:
            # Handle case where table structure is different
            cursor.execute('SELECT permanent_id, machine_id, created_date, last_used_date, linked_email, device_name FROM device_info LIMIT 1')
            result = cursor.fetchone()
            if result:
                result = result + (False,)  # Add default registered_online value
        
        conn.close()
        
        if result:
            return {
                'permanent_id': result[1],
                'machine_id': result[2],
                'created_date': result[3],
                'last_used_date': result[4],
                'linked_email': result[5],
                'device_name': result[6],
                'registered_online': result[7] if len(result) > 7 else False
            }
        return {}

    def get_or_create_session(self, permanent_id: str) -> str:
        """Get or create a session for this device - one session per device"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Use permanent_id as session_id to ensure one session per device
        session_id = permanent_id
        
        # Check if session exists
        cursor.execute('SELECT session_id FROM usage_sessions WHERE session_id = ?', (session_id,))
        result = cursor.fetchone()
        
        if not result:
            # Create new session
            current_time = time.strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO usage_sessions 
                (session_id, permanent_id, total_minutes_used, files_processed, first_use_date, last_use_date)
                VALUES (?, ?, 0, 0, ?, ?)
            ''', (session_id, permanent_id, current_time, current_time))
        else:
            # Update last use date for existing session
            cursor.execute('''
                UPDATE usage_sessions 
                SET last_use_date = ?
                WHERE session_id = ?
            ''', (time.strftime('%Y-%m-%d %H:%M:%S'), session_id))
        
        conn.commit()
        conn.close()
        return session_id
    
    def get_session_usage(self, session_id: str) -> Dict[str, Any]:
        """Get usage statistics for a session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT total_minutes_used, files_processed, first_use_date, last_use_date, user_email
            FROM usage_sessions WHERE session_id = ?
        ''', (session_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'total_minutes_used': result[0],
                'files_processed': result[1],
                'first_use_date': result[2],
                'last_use_date': result[3],
                'user_email': result[4]
            }
        else:
            return {
                'total_minutes_used': 0,
                'files_processed': 0,
                'first_use_date': None,
                'last_use_date': None,
                'user_email': None
            }
    
    def record_usage(self, session_id: str, permanent_id: str, file_name: str, duration_minutes: float, user_email: str = None):
        """Record file processing usage locally"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_time = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Insert or update session
        cursor.execute('''
            INSERT OR REPLACE INTO usage_sessions 
            (session_id, permanent_id, total_minutes_used, files_processed, first_use_date, last_use_date, user_email)
            VALUES (?, ?, 
                COALESCE((SELECT total_minutes_used FROM usage_sessions WHERE session_id = ?), 0) + ?,
                COALESCE((SELECT files_processed FROM usage_sessions WHERE session_id = ?), 0) + 1,
                COALESCE((SELECT first_use_date FROM usage_sessions WHERE session_id = ?), ?),
                ?,
                COALESCE(?, (SELECT user_email FROM usage_sessions WHERE session_id = ?))
            )
        ''', (session_id, permanent_id, session_id, duration_minutes, session_id, session_id, current_time, current_time, user_email, session_id))
        
        # Record individual file
        cursor.execute('''
            INSERT INTO processed_files (session_id, permanent_id, file_name, duration_minutes, processed_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (session_id, permanent_id, file_name, duration_minutes, current_time))
        
        conn.commit()
        conn.close()
    
    def can_process_file(self, session_id: str, duration_minutes: float, free_limit: float = 60.0) -> Dict[str, Any]:
        """Check if user can process a file based on offline usage"""
        usage = self.get_session_usage(session_id)
        total_after_processing = usage['total_minutes_used'] + duration_minutes
        
        return {
            'allowed': total_after_processing <= free_limit,
            'current_usage': usage['total_minutes_used'],
            'remaining_minutes': max(0, free_limit - usage['total_minutes_used']),
            'would_exceed_by': max(0, total_after_processing - free_limit)
        }
    
    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get all usage sessions for admin reporting"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT session_id, permanent_id, total_minutes_used, files_processed, first_use_date, last_use_date, user_email
            FROM usage_sessions ORDER BY last_use_date DESC
        ''')
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                'session_id': row[0],
                'permanent_id': row[1],
                'total_minutes_used': row[2],
                'files_processed': row[3],
                'first_use_date': row[4],
                'last_use_date': row[5],
                'user_email': row[6]
            })
        
        conn.close()
        return sessions

class SaaSAPIClient:
    """
    API client for communication between Python silence cutter app and SaaS website
    """
    
    def __init__(self):
        self.base_url = os.getenv('SAAS_API_URL', 'http://localhost:3000/api')
        self.offline_tracker = OfflineUsageTracker()
        self.permanent_id = self.offline_tracker.get_or_create_permanent_id()
        # Use permanent_id as session_id to ensure one session per device
        self.session_id = self.offline_tracker.get_or_create_session(self.permanent_id)
        self.user_id = None
        self.user_email = None
        self.subscription_status = None
        
        # Register device with server on startup - check online for existing registration
        self._register_device_with_server()
        
    def _register_device_with_server(self):
        """Register this device with the server for admin tracking - always check online first"""
        try:
            device_info = self.offline_tracker.get_device_info()
            
            print(f"🔍 Checking device registration online...")
            
            # Always check if device exists online first
            check_payload = {
                'permanentId': self.permanent_id,
                'action': 'check_exists'
            }
            
            check_response = requests.post(
                f"{self.base_url}/register-device",
                json=check_payload,
                timeout=10
            )
            
            if check_response.status_code == 200:
                check_result = check_response.json()
                
                if check_result.get('exists'):
                    print(f"✅ Device found online, updating registration (ID: {self.permanent_id[:8]}...)")
                    # Update existing registration
                    update_payload = {
                        'permanentId': self.permanent_id,
                        'sessionId': self.session_id,
                        'deviceInfo': device_info,
                        'timestamp': int(time.time()),
                        'action': 'update'
                    }
                    
                    update_response = requests.post(
                        f"{self.base_url}/register-device",
                        json=update_payload,
                        timeout=10
                    )
                    
                    if update_response.status_code == 200:
                        self.offline_tracker.mark_device_registered_online(self.permanent_id)
                        print(f"✅ Device registration updated successfully")
                    else:
                        print(f"❌ Failed to update device registration: {update_response.status_code}")
                else:
                    print(f"🆕 Creating new device registration online (ID: {self.permanent_id[:8]}...)")
                    # Create new registration
                    create_payload = {
                        'permanentId': self.permanent_id,
                        'sessionId': self.session_id,
                        'deviceInfo': device_info,
                        'timestamp': int(time.time()),
                        'action': 'create'
                    }
                    
                    create_response = requests.post(
                        f"{self.base_url}/register-device",
                        json=create_payload,
                        timeout=10
                    )
                    
                    if create_response.status_code == 200:
                        self.offline_tracker.mark_device_registered_online(self.permanent_id)
                        print(f"✅ Device registered successfully (ID: {self.permanent_id[:8]}...)")
                    else:
                        print(f"❌ Failed to create device registration: {create_response.status_code}")
            else:
                print(f"❌ Server check failed with status: {check_response.status_code}")
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Could not connect to server: {self.base_url}")
            print(f"    Error: {e}")
            print(f"    Working in offline mode (ID: {self.permanent_id[:8]}...)")
            print(f"    Data will sync when server becomes available")
    
    def validate_file_usage(self, file_duration_minutes: float, user_identifier: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate if the user can process a file of given duration
        Checks both online (if connected) and offline usage
        """
        # First check offline usage for anonymous/offline users
        offline_check = self.offline_tracker.can_process_file(self.session_id, file_duration_minutes)
        
        try:
            payload = {
                'sessionId': self.session_id,
                'permanentId': self.permanent_id,
                'fileDuration': file_duration_minutes,
                'userIdentifier': user_identifier,
                'offlineUsage': self.offline_tracker.get_session_usage(self.session_id),
                'deviceInfo': self.offline_tracker.get_device_info()
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
                    
                    # Link email to device
                    self.offline_tracker.link_email_to_device(self.user_email)
                
                return {
                    'allowed': result.get('allowed', offline_check['allowed']),
                    'message': result.get('message', self._get_offline_message(offline_check, file_duration_minutes)),
                    'user': result.get('user'),
                    'requiresAuth': result.get('requiresAuth', not offline_check['allowed']),
                    'remainingMinutes': result.get('remainingMinutes', offline_check['remaining_minutes']),
                    'upgradeUrl': result.get('upgradeUrl', ''),
                    'offlineUsage': offline_check,
                    'permanentId': self.permanent_id
                }
            else:
                # Fallback to offline checking if server is unavailable
                return {
                    'allowed': offline_check['allowed'],
                    'message': self._get_offline_message(offline_check, file_duration_minutes),
                    'user': None,
                    'requiresAuth': not offline_check['allowed'],
                    'remainingMinutes': offline_check['remaining_minutes'],
                    'upgradeUrl': '/pricing',
                    'offlineUsage': offline_check,
                    'offline_mode': True,
                    'permanentId': self.permanent_id
                }
                
        except requests.exceptions.RequestException as e:
            print(f"API request failed, using offline mode: {e}")
            return {
                'allowed': offline_check['allowed'],
                'message': self._get_offline_message(offline_check, file_duration_minutes),
                'user': None,
                'requiresAuth': not offline_check['allowed'],
                'remainingMinutes': offline_check['remaining_minutes'],
                'upgradeUrl': '/pricing',
                'offlineUsage': offline_check,
                'offline_mode': True,
                'error': True,
                'permanentId': self.permanent_id
            }
    
    def _get_offline_message(self, offline_check: Dict[str, Any], file_duration: float) -> str:
        """Generate appropriate message for offline usage check"""
        if offline_check['allowed']:
            return f"You can process this {file_duration:.1f} minute file. You have {offline_check['remaining_minutes']:.1f} minutes remaining in your free quota."
        else:
            return f"This file is {file_duration:.1f} minutes long, which would exceed your free limit by {offline_check['would_exceed_by']:.1f} minutes. Please sign up for unlimited processing."
    
    def record_usage(self, file_duration_minutes: float = None, file_name: str = None, 
                     file_path: str = None, duration_minutes: float = None, processing_type: str = None) -> bool:
        """
        Record the usage of a processed file both locally and online
        Support both new and legacy parameter formats for backward compatibility
        """
        # Handle legacy parameter format
        if file_path is not None and duration_minutes is not None:
            # Legacy format: record_usage(file_path=..., duration_minutes=..., processing_type=...)
            if file_name is None:
                file_name = os.path.basename(file_path) if file_path else "unknown_file"
            if file_duration_minutes is None:
                file_duration_minutes = duration_minutes
        
        # CRITICAL FIX: Detect and correct wrong duration calculations (file size based)
        if file_duration_minutes is not None and file_duration_minutes > 10 and file_path is not None:
            # Duration seems suspiciously high - let's verify with proper video duration detection
            print(f"⚠️ Duration {file_duration_minutes:.1f} min seems high, verifying actual video duration...")
            
            correct_duration = None
            
            # Method 1: Try moviepy
            try:
                import moviepy.editor as mp
                with mp.VideoFileClip(file_path) as video:
                    if video.duration and video.duration > 0:
                        correct_duration = video.duration / 60
                        print(f"✅ Corrected duration using moviepy: {correct_duration:.2f} minutes")
            except Exception as e:
                print(f"⚠️ MoviePy verification failed: {e}")
            
            # Method 2: Try FFmpeg probe if moviepy failed
            if correct_duration is None:
                try:
                    import subprocess
                    import json
                    result = subprocess.run([
                        'ffprobe', '-v', 'quiet', '-print_format', 'json', 
                        '-show_format', file_path
                    ], capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        probe_data = json.loads(result.stdout)
                        duration_seconds = float(probe_data['format']['duration'])
                        correct_duration = duration_seconds / 60
                        print(f"✅ Corrected duration using FFprobe: {correct_duration:.2f} minutes")
                except Exception as e:
                    print(f"⚠️ FFprobe verification failed: {e}")
            
            # If we found a more reasonable duration, use it
            if correct_duration is not None and correct_duration < file_duration_minutes:
                print(f"🔧 Correcting duration from {file_duration_minutes:.1f} to {correct_duration:.2f} minutes")
                file_duration_minutes = correct_duration
        
        # Validate we have the required parameters
        if file_duration_minutes is None or file_name is None:
            print("❌ Missing required parameters for record_usage")
            return False
        
        # Ensure duration is reasonable (between 0.1 and 500 minutes)
        file_duration_minutes = max(0.1, min(500.0, file_duration_minutes))
        
        # Always record locally first
        self.offline_tracker.record_usage(self.session_id, self.permanent_id, file_name, file_duration_minutes, self.user_email)
        print(f"📊 Recorded usage locally: {file_name} ({file_duration_minutes:.2f} min)")
        
        # Try to sync with server
        try:
            payload = {
                'sessionId': self.session_id,
                'permanentId': self.permanent_id,
                'fileDuration': file_duration_minutes,
                'fileName': file_name,
                'userId': self.user_id,
                'timestamp': int(time.time()),
                'offlineUsage': self.offline_tracker.get_session_usage(self.session_id),
                'deviceInfo': self.offline_tracker.get_device_info()
            }
            
            print(f"🌐 Syncing to server: {self.base_url}/record-usage")
            
            response = requests.post(
                f"{self.base_url}/record-usage",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Successfully synced to server")
                return True
            else:
                print(f"❌ Server responded with status {response.status_code}: {response.text}")
                return False
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to sync usage to server: {e}")
            print(f"💾 Data saved locally and will sync when server is available")
            return True  # Still return True since we recorded locally
    
    def sync_offline_usage(self) -> bool:
        """
        Sync offline usage data to server when connection is available
        """
        try:
            sessions = self.offline_tracker.get_all_sessions()
            
            payload = {
                'sessionId': self.session_id,
                'permanentId': self.permanent_id,
                'offlineSessions': sessions,
                'deviceInfo': self.offline_tracker.get_device_info()
            }
            
            response = requests.post(
                f"{self.base_url}/sync-offline-usage",
                json=payload,
                timeout=15
            )
            
            return response.status_code == 200
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to sync offline usage: {e}")
            return False

    def authenticate_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user with email and password
        """
        try:
            payload = {
                'email': email,
                'password': password,
                'sessionId': self.session_id,
                'permanentId': self.permanent_id,
                'deviceInfo': self.offline_tracker.get_device_info()
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
                    
                    # Link email to permanent device ID
                    self.offline_tracker.link_email_to_device(email)
                    
                    # Sync offline usage after successful login
                    self.sync_offline_usage()
                
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
        """
        if not self.user_id:
            return None
            
        try:
            response = requests.get(
                f"{self.base_url}/user/{self.user_id}",
                params={
                    'sessionId': self.session_id,
                    'permanentId': self.permanent_id
                },
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
        """
        return f"{self.base_url.replace('/api', '')}/auth/signin?session={self.session_id}&device={self.permanent_id}"
    
    def open_upgrade_page(self) -> str:
        """
        Generate URL for upgrade page
        """
        return f"{self.base_url.replace('/api', '')}/pricing?session={self.session_id}&device={self.permanent_id}"
    
    def check_subscription_status(self) -> Optional[Dict[str, Any]]:
        """
        Check current subscription status
        """
        if not self.user_id:
            return None
            
        try:
            response = requests.get(
                f"{self.base_url}/subscription/status",
                params={
                    'userId': self.user_id,
                    'sessionId': self.session_id,
                    'permanentId': self.permanent_id
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
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get current session statistics for display
        """
        offline_usage = self.offline_tracker.get_session_usage(self.session_id)
        device_info = self.offline_tracker.get_device_info()
        
        return {
            'session_id': self.session_id,
            'permanent_id': self.permanent_id,
            'total_minutes_used': offline_usage['total_minutes_used'],
            'files_processed': offline_usage['files_processed'],
            'remaining_free_minutes': max(0, 60 - offline_usage['total_minutes_used']),
            'user_email': self.user_email or device_info.get('linked_email'),
            'subscription_status': self.subscription_status,
            'device_info': device_info
        }

# Global instance for the application
api_client = SaaSAPIClient() 