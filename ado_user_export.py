#!/usr/bin/env python3
"""
Azure DevOps User Export Tool
Exports all users from an Azure DevOps organization with their access levels and other information
"""

import os
import sys
import argparse
import logging
import requests
import base64
from datetime import datetime, timedelta

# API URL Templates
ADO_API_BASE_URL = "https://vsaex.dev.azure.com/{org}/_apis/userentitlements"
ADO_API_VERSION = "api-version=7.1"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ado_user_export')

def get_config(key, default=None, required=False):
    """Get configuration from environment variables or config file"""
    # Try environment variable first
    value = os.environ.get(key)
    
    # If still not found and required, exit
    if not value and required:
        logger.error(f"{key} is required but not defined in environment or config file")
        sys.exit(1)
    
    # Return value or default
    return value or default

def check_env_var(var_name):
    """Check if an environment variable exists and is not empty"""
    return get_config(var_name, required=True)

def format_date(date_str: str) -> str:
    """Format date from API to YYYY-MM-DD or 'never'
    
    Args:
        date_str (str): Date string from API
        
    Returns:
        str: Formatted date string
    """
    if not date_str or date_str == "0001-01-01T00:00:00Z":
        return "never"
    
    try:
        # Simply extract the date portion before the 'T'
        if 'T' in date_str:
            return date_str.split('T')[0]
        return date_str  # Return as-is if no 'T' found
    except Exception as e:
        logger.debug(f"Error parsing date {date_str}: {e}")
        return date_str

def get_ado_users(org: str, token: str) -> dict:
    """Retrieve all users from the Azure DevOps organization
    
    Args:
        org (str): Azure DevOps organization name
        token (str): Personal Access Token (PAT) for authentication
        
    Returns:
        dict: User data retrieved from Azure DevOps API or error information
    """
    url = f"{ADO_API_BASE_URL.format(org=org)}?{ADO_API_VERSION}"
    
    # Create basic auth header with empty username and PAT as password
    auth_str = base64.b64encode(f":{token}".encode()).decode()
    headers = {
        "Accept": "application/json",
        "Authorization": f"Basic {auth_str}"
    }
    
    logger.debug(f"Requesting users from {url}")
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        error_message = ""
        if response.text:
            error_message = response.text
            
        logger.error(f"API request failed with status code: {response.status_code}")
        logger.error(f"Response: {error_message}")
        
        if response.status_code == 401:
            logger.error("Authentication failed. Please check if your token is valid and has not expired.")
        
        return {"error": True, "status_code": response.status_code, "message": error_message}
    
    return response.json()

def filter_inactive_users(users_data: dict, days: int) -> dict:
    """
    Filter users who haven't accessed ADO in the specified number of days
    
    Args:
        users_data (dict): Dictionary containing user data from ADO API
        days (int): Number of days to check for inactivity
        
    Returns:
        dict: Filtered user data containing only inactive users
    """
    # Skip filtering if there was an error or if days is not specified
    if users_data.get("error") or not days:
        return users_data
    
    filtered_items = []
    today = datetime.now().date()
    cutoff_date = today - timedelta(days=days)
    
    for item in users_data.get("items", []):
        last_access = item.get("lastAccessedDate", "")
        
        # Skip users who have never accessed
        if not last_access or last_access == "0001-01-01T00:00:00Z":
            continue
        
        try:
            # Parse the date and compare
            last_access_date = datetime.strptime(last_access.split('T')[0], "%Y-%m-%d").date()
            if last_access_date <= cutoff_date:
                filtered_items.append(item)
        except Exception as e:
            logger.debug(f"Error parsing date {last_access}: {e}")
    
    # Return a new users_data object with filtered items
    return {"count": len(filtered_items), "items": filtered_items}

def format_users_as_csv(users_data: dict) -> str:
    """
    Format users data as CSV string
    
    Args:
        users_data (dict): Dictionary containing user data from ADO API
        
    Returns:
        str: CSV formatted string with user data
    """
    # Return empty string if there was an error
    if users_data.get("error"):
        return ""
    
    csv_lines = []
    
    # Get the items
    items = users_data.get("items", [])
    
    # Add header only if there are users
    if items:
        csv_lines.append("Username,Name,Access Level,Last Access,Date Created,License Status,License Source")
    
    # Add each user as a row
    for item in items:
        user = item.get("user", {})
        access_level = item.get("accessLevel", {})
        
        # Extract required fields
        name = user.get("displayName", "")
        username = user.get("principalName", "")
        access_level_name = access_level.get("licenseDisplayName", "")
        last_access = format_date(item.get("lastAccessedDate", ""))
        date_created = format_date(item.get("dateCreated", ""))
        license_status = access_level.get("status", "")
        license_source = access_level.get("licensingSource", "")
        
        # Create CSV row, escaping commas in fields if necessary
        row = f"{username},{name},{access_level_name},{last_access},{date_created},{license_status},{license_source}"
        csv_lines.append(row)
    
    return "\n".join(csv_lines)

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Export Azure DevOps users with access levels')
    parser.add_argument('--output', help='Output file path')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--inactive-in-last-days', type=int, help='Only show users who have not logged in for the specified number of days')
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Get configuration 
    token = get_config("ADO_TOKEN", required=True)
    org = get_config("ADO_ORG", required=True)
    
    logger.debug(f"Using organization: {org}")
    
    # Get users from ADO
    users_data = get_ado_users(org, token)
    
    # Exit if there was an API error
    if users_data.get("error"):
        sys.exit(1)
    
    logger.debug(f"Retrieved {len(users_data.get('items', []))} users")
    
    # Filter inactive users if requested
    if args.inactive_in_last_days:
        logger.info(f"Filtering users inactive in the last {args.inactive_in_last_days} days")
        original_count = len(users_data.get('items', []))
        users_data = filter_inactive_users(users_data, args.inactive_in_last_days)
        filtered_count = len(users_data.get('items', []))
        logger.info(f"Filtered from {original_count} to {filtered_count} users")
    
    # Format as CSV
    csv_content = format_users_as_csv(users_data)
    
    # Only proceed if we have content
    if csv_content:
        # Output to file if specified
        if args.output:
            try:
                with open(args.output, 'w') as f:
                    f.write(csv_content)
                logger.info(f"User data written to {args.output}")
            except Exception as e:
                logger.error(f"Error writing to file {args.output}: {e}")
        
        # Always print to stdout
        print(csv_content)
    else:
        logger.error("No data to output")

if __name__ == "__main__":
    main()
