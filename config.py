import os
import requests
from typing import List, Dict, Optional


# ============================================================
# BASIC CONFIGURATION
# ============================================================

# API Configuration
API_VERSION_FALLBACK = '50.0'  # Universal fallback supported by all orgs

# Directories
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# GUI Configuration
WINDOW_TITLE = "Salesforce Picklist Exporter"
WINDOW_GEOMETRY = "1200x800"
APPEARANCE_MODE = "System"
COLOR_THEME = "blue"

# Export Configuration
DEFAULT_PICKLIST_FILENAME = 'Picklist_Export_{timestamp}.xlsx'
DEFAULT_METADATA_FILENAME = 'Object_Metadata_{timestamp}.csv'


# ============================================================
# API VERSION DETECTOR CLASS
# ============================================================

class APIVersionDetector:
    """Detects the latest available API version from a Salesforce org"""
    
    @staticmethod
    def get_latest_version_from_org(base_url: str, headers: dict, 
                                     fallback_version: str = '50.0') -> str:
        """
        Detect the LATEST API version available in the connected org
        
        Args:
            base_url: Salesforce instance URL (e.g., https://na123.salesforce.com)
            headers: Authentication headers with Bearer token
            fallback_version: Version to use if detection fails (default: 50.0)
            
        Returns:
            Latest API version as string (e.g., '64.0', '54.0', '60.0')
        """
        try:
            # Query the versions endpoint - lists ALL available versions for the org
            url = f"{base_url}/services/data/"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                versions = response.json()
                if versions and isinstance(versions, list) and len(versions) > 0:
                    # Get the LAST version in the list (the latest one)
                    latest = versions[-1]
                    version = latest.get('version', fallback_version)
                    print(f"✅ Detected org's latest API version: {version}")
                    return version
                else:
                    print(f"⚠️ No versions returned, using fallback: {fallback_version}")
                    return fallback_version
            else:
                print(f"⚠️ Version endpoint returned {response.status_code}, using fallback: {fallback_version}")
                return fallback_version
            
        except Exception as e:
            print(f"⚠️ API version detection failed: {str(e)}")
            print(f"   Using fallback version: {fallback_version}")
            return fallback_version
    
    @staticmethod
    def get_all_available_versions(base_url: str, headers: dict) -> List[Dict]:
        """
        Get ALL available API versions from the org
        
        Returns:
            List of version dictionaries: [{'version': '54.0', 'label': 'Winter 25', 'url': '...'}, ...]
        """
        try:
            url = f"{base_url}/services/data/"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                versions = response.json()
                print(f"📋 Available API versions in org: {[v['version'] for v in versions]}")
                return versions
            
            return []
            
        except Exception as e:
            print(f"⚠️ Failed to get available versions: {str(e)}")
            return []
    
    @staticmethod
    def is_version_supported(base_url: str, headers: dict, version: str) -> bool:
        """
        Check if a specific API version is supported
        
        Args:
            base_url: Salesforce instance URL
            headers: Authentication headers
            version: Version to check (e.g., '65.0')
            
        Returns:
            True if version is supported, False otherwise
        """
        try:
            url = f"{base_url}/services/data/v{version}/"
            response = requests.get(url, headers=headers, timeout=10)
            return response.status_code == 200
        except:
            return False
