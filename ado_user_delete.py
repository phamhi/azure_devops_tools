#!/usr/bin/env python3
"""
Azure DevOps User Deletion Tool
Deletes users from an Azure DevOps organization based on a list of usernames from a text file
"""

import os
import sys
import argparse
import logging
import requests
import csv
import base64
from typing import List, Dict, Tuple, Optional, Any

# API URL Templates
ADO_API_BASE_URL = "https://vsaex.dev.azure.com/{org}/_apis/userentitlements"
ADO_API_VERSION = "api-version=7.1"

# Result Status Constants
STATUS_SUCCESS = "DELETED_SUCCESSFULLY"
STATUS_NOT_FOUND = "NOT_FOUND"
STATUS_ERROR = "UNKNOWN_ERROR"
STATUS_PERMISSION_ERROR = "PERMISSION_ERROR"  # New status for permission issues

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ado_user_delete')

def get_config(key: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """Get configuration from environment variables or config file"""
    # Try environment variable first
    value = os.environ.get(key)
    
    # If still not found and required, exit
    if not value and required:
        logger.error(f"{key} is required but not defined in environment")
        sys.exit(1)
    
    # Return value or default
    return value or default

def read_usernames_from_file(file_path: str) -> List[str]:
    """
    Read usernames from a text file (one username per line)
    
    Args:
        file_path (str): Path to the text file
        
    Returns:
        list: List of usernames
    """
    usernames: List[str] = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                # Strip whitespace and ignore empty lines
                username = line.strip()
                if username:
                    usernames.append(username)
                    
        logger.debug(f"Read {len(usernames)} usernames from {file_path}")
        return usernames
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        sys.exit(1)

def get_user_id(org: str, token: str, username: str) -> Optional[str]:
    """
    Get user ID from username
    
    Args:
        org (str): Azure DevOps organization name
        token (str): Personal Access Token (PAT) for authentication
        username (str): Username to look up
        
    Returns:
        str: User ID or None if not found
    """
    url = f"{ADO_API_BASE_URL.format(org=org)}?{ADO_API_VERSION}"
    
    # Create basic auth header with empty username and PAT as password
    auth_str = base64.b64encode(f":{token}".encode()).decode()
    headers = {
        "Accept": "application/json",
        "Authorization": f"Basic {auth_str}"
    }
    
    try:
        logger.debug(f"Looking up user ID for {username}")
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"API request failed with status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
        
        users_data = response.json()
        for item in users_data.get("items", []):
            user = item.get("user", {})
            if user.get("principalName", "").lower() == username.lower():
                return item.get("id")
        
        return None
    except Exception as e:
        logger.error(f"Error getting user ID for {username}: {e}")
        return None

def delete_user(org: str, token: str, user_id: str) -> Tuple[str, str]:
    """
    Delete user from Azure DevOps
    
    Args:
        org (str): Azure DevOps organization name
        token (str): Personal Access Token (PAT) for authentication
        user_id (str): User ID to delete
        
    Returns:
        tuple: (status, error_message)
    """
    url = f"{ADO_API_BASE_URL.format(org=org)}/{user_id}?{ADO_API_VERSION}"
    
    # Create basic auth header with empty username and PAT as password
    auth_str = base64.b64encode(f":{token}".encode()).decode()
    headers = {
        "Accept": "application/json",
        "Authorization": f"Basic {auth_str}"
    }
    
    try:
        logger.debug(f"Deleting user with ID {user_id} from {url}")
        response = requests.delete(url, headers=headers)
        
        if response.status_code == 204:  # Successful deletion
            return (STATUS_SUCCESS, "")
        elif response.status_code == 403:  # Permission error
            error_message = "Permission denied."
            try:
                error_message += f" Details: {response.json().get('message', '')}"
            except:
                error_message += f" Details: {response.text}"
            return (STATUS_PERMISSION_ERROR, error_message)
        else:
            error_message = f"API returned status code: {response.status_code}"
            try:
                error_message += f" - {response.json().get('message', '')}"
            except:
                error_message += f" - {response.text}"
            return (STATUS_ERROR, error_message)
    except Exception as e:
        return (STATUS_ERROR, str(e))

def process_deletions(org: str, token: str, usernames: List[str]) -> List[Dict[str, str]]:
    """
    Process user deletions and collect results
    
    Args:
        org (str): Azure DevOps organization name
        token (str): Personal Access Token (PAT) for authentication
        usernames (list): List of usernames to delete
        
    Returns:
        list: List of dictionaries with deletion results
    """
    results: List[Dict[str, str]] = []
    
    for username in usernames:
        result: Dict[str, str] = {
            "username": username,
            "status": "",
            "error": ""
        }
        
        # Get user ID
        user_id: Optional[str] = get_user_id(org, token, username)
        
        if not user_id:
            result["status"] = STATUS_NOT_FOUND
        else:
            # Delete user
            status, error = delete_user(org, token, user_id)
            result["status"] = status
            result["error"] = error
        
        results.append(result)
        logger.info(f"Processed {username}: {result['status']}")
    
    return results

def write_results_to_csv(results: List[Dict[str, str]], output_file: str) -> None:
    """
    Write deletion results to CSV
    
    Args:
        results (list): List of dictionaries with deletion results
        output_file (str): Path to output file
    """
    try:
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["username", "status", "error"])
            
            for result in results:
                writer.writerow([
                    result["username"],
                    result["status"],
                    result["error"]
                ])
        
        logger.info(f"Results written to {output_file}")
    except Exception as e:
        logger.error(f"Error writing results to {output_file}: {e}")

def main() -> None:
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Delete Azure DevOps users from a text file')
    parser.add_argument('--input', required=True, help='Input file path containing usernames (one per line)')
    parser.add_argument('--output', help='Output file path for deletion results')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--no-dry-run', action='store_true', help='Execute actual deletions (default is dry run)')
    args: argparse.Namespace = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Get configuration 
    token: str = get_config("ADO_TOKEN", required=True)
    org: str = get_config("ADO_ORG", required=True)
    
    # Read usernames from file
    usernames: List[str] = read_usernames_from_file(args.input)
    logger.info(f"Found {len(usernames)} usernames to process")
    
    # Default is dry run unless --no-dry-run is specified
    dry_run = not args.no_dry_run
    if dry_run:
        logger.info("DRY RUN MODE: No users will actually be deleted")
        results: List[Dict[str, str]] = []
        for username in usernames:
            results.append({
                "username": username,
                "status": "DRY_RUN",
                "error": ""
            })
    else:
        # Process deletions
        results: List[Dict[str, str]] = process_deletions(org, token, usernames)
    
    # Generate output
    if args.output:
        write_results_to_csv(results, args.output)
    
    # Print summary
    success_count: int = sum(1 for r in results if r["status"] == STATUS_SUCCESS)
    not_found_count: int = sum(1 for r in results if r["status"] == STATUS_NOT_FOUND)
    permission_error_count: int = sum(1 for r in results if r["status"] == STATUS_PERMISSION_ERROR)
    error_count: int = sum(1 for r in results if r["status"] == STATUS_ERROR)
    
    print("\nDeletion Summary:")
    print(f"  Successfully deleted: {success_count}")
    print(f"  Not found: {not_found_count}")
    print(f"  Permission errors: {permission_error_count}")
    print(f"  Other errors: {error_count}")
    
    # Also print results to stdout
    print("\nResults:")
    print("username,status,error")
    for result in results:
        print(f"{result['username']},{result['status']},{result['error']}")

if __name__ == "__main__":
    main()
