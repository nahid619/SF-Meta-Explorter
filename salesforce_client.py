"""
Salesforce connection and authentication handler
"""
from typing import List, Optional, Callable
from simple_salesforce import Salesforce
#from config import API_VERSION
from config import API_VERSION_FALLBACK, APIVersionDetector


class SalesforceClient:
    """Handles Salesforce authentication and connection"""
    
    def __init__(self, username: str, password: str, security_token: str, 
                domain: str = 'login', status_callback=None):
       
       self.status_callback = status_callback
       self.all_org_objects = []
       self.api_version = API_VERSION_FALLBACK  # ADD THIS LINE
       
       self._log_status("🔌 Initializing Salesforce Connection...")
       
       try:
           # Connect to Salesforce
           self.sf = Salesforce(
               username=username,
               password=password,
               security_token=security_token,
               domain=domain
           )
           self.base_url = f"https://{self.sf.sf_instance}"
           self.session_id = self.sf.session_id
           self.headers = {
               'Authorization': f'Bearer {self.session_id}',
               'Content-Type': 'application/json'
           }
           self._log_status(f"✅ Connected to: {self.base_url}")
           
           # ADD THESE LINES - Detect org's API version
           self._log_status("🔍 Detecting org's API version...")
           self.api_version = APIVersionDetector.get_latest_version_from_org(
               self.base_url, 
               self.headers, 
               fallback_version=API_VERSION_FALLBACK
           )
           self._log_status(f"📡 Using API Version: v{self.api_version}")
           
           # Continue with existing code
           self._fetch_all_org_objects()
       
       except Exception as e:
           self._log_status(f"❌ Connection failed: {str(e)}")
           raise

    def _fetch_all_org_objects(self):
        """Fetches all SObjects (Standard and Custom) from the org"""
        self._log_status("Fetching all available SObjects from the organization...")
        try:
            response = self.sf.describe()
            self.all_org_objects = sorted([
                obj['name'] for obj in response['sobjects'] 
                if obj.get('queryable', False) and not obj.get('deprecatedAndHidden', False)
            ])
            self._log_status(f"✅ Found {len(self.all_org_objects)} queryable objects.")
        except Exception as e:
            self._log_status(f"❌ Failed to fetch all SObjects: {str(e)}")
            self.all_org_objects = []
    
    def get_all_objects(self) -> List[str]:
        """Accessor for the fetched object list"""
        return self.all_org_objects
    
    def _log_status(self, message: str):
        """Internal helper to send log messages back to the GUI"""
        if self.status_callback:
            self.status_callback(message, verbose=True)
            
    def get_api_version(self) -> str:
       """Get the current API version being used"""
       return self.api_version
