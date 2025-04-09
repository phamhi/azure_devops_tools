#!/usr/bin/env python3
"""
Azure DevOps User Export Tool
Exports all users from an Azure DevOps organization with their access levels and other information,
handling pagination to retrieve all users.
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
ADO_API_VERSION = "api-version=7.1" # Use a specific, tested version

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ado_user_export')

def get_config(key, default=None, required=False):
    """Get configuration from environment variables"""
    value = os.environ.get(key)
    if not value and required:
        logger.error(f"{key} is required but not defined as an environment variable.")
        sys.exit(1)
    return value or default

def check_env_var(var_name):
    """Check if an environment variable exists and is not empty"""
    # This function is essentially covered by get_config with required=True
    # Keeping it for potential future use if logic differs
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
        # Attempt parsing if it's already just a date
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
         logger.debug(f"Date string {date_str} is not in expected YYYY-MM-DDTHH:MM:SSZ or YYYY-MM-DD format.")
         return date_str # Return original if format is unexpected
    except Exception as e:
        logger.debug(f"Error parsing date {date_str}: {e}")
        return date_str # Return original on other errors

def get_ado_users(org: str, token: str) -> dict:
    """Retrieve ALL users from the Azure DevOps organization using pagination.

    Args:
        org (str): Azure DevOps organization name
        token (str): Personal Access Token (PAT) for authentication

    Returns:
        dict: User data retrieved from Azure DevOps API or error information
              Structure: {"count": int, "items": list, "error": bool, "status_code": int|None, "message": str|None}
    """
    all_users_items = []
    continuation_token = None
    # Use the search endpoint which explicitly supports pagination via continuation token
    # Note: The base URL provided in the original script might also support it, but search is clearer.
    # Let's stick to the original endpoint as requested, assuming it supports the header token.
    base_url = f"{ADO_API_BASE_URL.format(org=org)}?{ADO_API_VERSION}"

    # Create basic auth header
    auth_str = base64.b64encode(f":{token}".encode()).decode()
    headers = {
        "Accept": "application/json",
        "Authorization": f"Basic {auth_str}"
    }

    page_num = 1
    max_pages = 1000 # Safety break to prevent infinite loops in unexpected scenarios
    while page_num <= max_pages: # Loop until no more continuation token or max pages hit

        # Construct URL for the current page
        current_url = base_url
        if continuation_token:
            # Ensure continuationToken is URL-encoded if it contains special characters (usually not needed for ADO tokens)
            # from urllib.parse import quote
            # current_url += f"&continuationToken={quote(continuation_token)}"
            current_url += f"&continuationToken={continuation_token}" # Usually safe without encoding

        logger.debug(f"Requesting users page {page_num} from {current_url}")
        try:
            response = requests.get(current_url, headers=headers, timeout=30) # Added timeout
            response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)

        except requests.exceptions.Timeout:
            logger.error(f"Request timed out while fetching page {page_num}.")
            if page_num == 1:
                 return {"error": True, "status_code": None, "message": "Request timed out on first page.", "items": [], "count": 0}
            else:
                 logger.warning(f"Timeout fetching page {page_num}, returning potentially incomplete data.")
                 break # Exit loop on timeout after first page

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            error_message = e.response.text or f"HTTP Error {status_code}"
            logger.error(f"API request failed on page {page_num} with status code: {status_code}")
            logger.error(f"Response: {error_message[:500]}...") # Log first 500 chars
            if status_code == 401:
                logger.error("Authentication failed. Check token validity and permissions (e.g., 'Member Entitlement Management' > Read).")
            # Return error if the first page fails, otherwise log and break (might have partial data)
            if page_num == 1:
                 return {"error": True, "status_code": status_code, "message": error_message, "items": [], "count": 0}
            else:
                 logger.warning(f"Failed fetching page {page_num}, returning potentially incomplete data.")
                 break # Exit loop on error after first page

        except requests.exceptions.RequestException as e:
            # Catch other potential network/request errors
            logger.error(f"A network or request error occurred on page {page_num}: {e}")
            if page_num == 1:
                 return {"error": True, "status_code": None, "message": f"Request Exception: {e}", "items": [], "count": 0}
            else:
                 logger.warning(f"Request exception on page {page_num}, returning potentially incomplete data.")
                 break # Exit loop

        # Process successful response
        try:
            data = response.json()
            page_items = data.get("items", [])
            if not page_items and page_num == 1:
                 logger.info("Initial API response contains no user items.")
                 # Still check for token in case of empty first page but more pages (unlikely but possible)

            all_users_items.extend(page_items)
            logger.info(f"Fetched {len(page_items)} users on page {page_num}. Total fetched so far: {len(all_users_items)}")

            # Check for continuation token in headers for the *next* request
            # Header name is typically 'x-ms-continuationtoken' for Azure APIs
            continuation_token = response.headers.get('x-ms-continuationtoken')

            if not continuation_token:
                logger.info(f"No continuation token found in headers for page {page_num}. Reached the last page.")
                break # Exit loop if no token
            else:
                 logger.debug(f"Found continuation token for next page: {continuation_token[:15]}...") # Log truncated token
                 page_num += 1

        except requests.exceptions.JSONDecodeError as e:
             logger.error(f"Failed to decode JSON response on page {page_num}: {e}")
             logger.error(f"Response text: {response.text[:500]}...") # Log beginning of text
             if page_num == 1:
                 return {"error": True, "status_code": response.status_code, "message": f"JSON Decode Error: {e}", "items": [], "count": 0}
             else:
                 logger.warning(f"JSON decode error on page {page_num}, returning potentially incomplete data.")
                 break # Exit loop

        except Exception as e: # Catch other potential errors during processing
            logger.error(f"An unexpected error occurred processing page {page_num}: {e}", exc_info=True) # Log traceback
            if page_num == 1:
                return {"error": True, "status_code": response.status_code, "message": f"Unexpected Error: {e}", "items": [], "count": 0}
            else:
                logger.warning(f"Unexpected error on page {page_num}, returning potentially incomplete data.")
                break # Exit loop

    if page_num > max_pages:
        logger.warning(f"Reached maximum page limit ({max_pages}). Result set might be incomplete.")

    # Return the aggregated data in the expected format
    return {"count": len(all_users_items), "items": all_users_items, "error": False, "status_code": 200, "message": "Success"}

def filter_inactive_users(users_data: dict, days: int) -> dict:
    """
    Filter users who haven't accessed ADO in the specified number of days
    (Operates on the dictionary structure returned by get_ado_users)

    Args:
        users_data (dict): Dictionary containing user data from ADO API
        days (int): Number of days to check for inactivity

    Returns:
        dict: Filtered user data containing only inactive users (maintains structure)
    """
    # Skip filtering if there was an error or if days is not specified or invalid
    if users_data.get("error") or not days or days <= 0:
        return users_data

    filtered_items = []
    # Use timezone-naive comparison for simplicity, assuming server times are consistent enough
    # For precise timezone handling, use dateutil.parser and aware datetime objects
    today = datetime.now().date()
    cutoff_date = today - timedelta(days=days)
    logger.info(f"Filtering for users with last access date <= {cutoff_date}")

    for item in users_data.get("items", []):
        last_access_str = item.get("lastAccessedDate", "")

        # Skip users who have never accessed
        if not last_access_str or last_access_str == "0001-01-01T00:00:00Z":
            logger.debug(f"Skipping user {item.get('user', {}).get('principalName', 'N/A')} - never accessed.")
            continue

        try:
            # Parse the date part only
            last_access_date = datetime.strptime(last_access_str.split('T')[0], "%Y-%m-%d").date()
            if last_access_date <= cutoff_date:
                filtered_items.append(item)
                logger.debug(f"Including inactive user {item.get('user', {}).get('principalName', 'N/A')} - last access: {last_access_date}")
            else:
                 logger.debug(f"Skipping active user {item.get('user', {}).get('principalName', 'N/A')} - last access: {last_access_date}")
        except ValueError:
            logger.warning(f"Could not parse lastAccessedDate '{last_access_str}' for user {item.get('user', {}).get('principalName', 'N/A')}. Skipping inactivity check for this user.")
        except Exception as e:
            logger.error(f"Error processing lastAccessedDate '{last_access_str}' for user {item.get('user', {}).get('principalName', 'N/A')}: {e}. Skipping inactivity check.")

    # Return a new users_data object with filtered items and updated count
    # Keep original error status etc. if they existed
    return {
        "count": len(filtered_items),
        "items": filtered_items,
        "error": users_data.get("error", False),
        "status_code": users_data.get("status_code"),
        "message": users_data.get("message")
        }

def format_users_as_csv(users_data: dict) -> str:
    """
    Format users data as CSV string

    Args:
        users_data (dict): Dictionary containing user data from ADO API

    Returns:
        str: CSV formatted string with user data, or empty string if no items or error.
    """
    # Return empty string if there was an error or no items
    if users_data.get("error") or not users_data.get("items"):
        if users_data.get("error"):
             logger.error("Cannot format CSV due to previous API error.")
        elif not users_data.get("items"):
             logger.info("No user items to format into CSV.")
        return ""

    csv_lines = []

    # Add header
    csv_lines.append("Username,Name,Access Level,Last Access,Date Created,License Status,License Source")

    # Add each user as a row
    items = users_data.get("items", [])
    for item in items:
        user = item.get("user", {})
        access_level = item.get("accessLevel", {})

        # Extract required fields, providing defaults for missing ones
        name = user.get("displayName", "N/A")
        username = user.get("principalName", "N/A") # Often the email/UPN
        access_level_name = access_level.get("licenseDisplayName", "N/A")
        last_access = format_date(item.get("lastAccessedDate", ""))
        date_created = format_date(item.get("dateCreated", ""))
        license_status = access_level.get("status", "N/A") # e.g., 'active', 'disabled'
        license_source = access_level.get("licensingSource", "N/A") # e.g., 'account', 'msdn'

        # Basic CSV escaping: double quotes around fields containing commas or quotes
        def escape_csv_field(field):
            field_str = str(field) # Ensure it's a string
            if '"' in field_str or ',' in field_str or '\n' in field_str:
                return '"' + field_str.replace('"', '""') + '"' # Escape quotes by doubling them
            return field_str

        # Create CSV row
        row_fields = [
            escape_csv_field(username),
            escape_csv_field(name),
            escape_csv_field(access_level_name),
            escape_csv_field(last_access),
            escape_csv_field(date_created),
            escape_csv_field(license_status),
            escape_csv_field(license_source)
        ]
        csv_lines.append(",".join(row_fields))

    return "\n".join(csv_lines)

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Export Azure DevOps users with access levels. Requires ADO_ORG and ADO_TOKEN environment variables.',
        epilog='Example: python export_users.py --output users.csv --inactive-in-last-days 90 --debug'
        )
    parser.add_argument('--output', help='Output file path for the CSV data.')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging.')
    parser.add_argument('--inactive-in-last-days', type=int, help='Only include users who have NOT accessed ADO in the specified number of days (e.g., 90).')
    args = parser.parse_args()

    # Set debug logging if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
        for handler in logging.root.handlers: # Ensure handlers also respect the level
            handler.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # Get configuration
    try:
        token = get_config("ADO_TOKEN", required=True)
        org = get_config("ADO_ORG", required=True)
    except SystemExit:
        # Error message already logged by get_config
        return # Exit cleanly

    logger.debug(f"Using organization: {org}")
    logger.info("Starting user retrieval process...")

    # Get users from ADO (handles pagination internally)
    users_data = get_ado_users(org, token)

    # Exit if there was an API error during retrieval
    if users_data.get("error"):
        logger.error(f"Failed to retrieve users. Error: {users_data.get('message', 'Unknown error')}")
        sys.exit(1)

    total_retrieved = users_data.get('count', 0)
    logger.info(f"Successfully retrieved {total_retrieved} total users from Azure DevOps.")

    # Filter inactive users if requested
    if args.inactive_in_last_days:
        if args.inactive_in_last_days <= 0:
             logger.warning("--inactive-in-last-days must be a positive integer. Skipping filtering.")
        else:
            logger.info(f"Filtering for users inactive in the last {args.inactive_in_last_days} days...")
            users_data = filter_inactive_users(users_data, args.inactive_in_last_days)
            filtered_count = users_data.get('count', 0)
            logger.info(f"Filtering complete. {filtered_count} users match the inactivity criteria.")


    # Format as CSV
    logger.info("Formatting user data as CSV...")
    csv_content = format_users_as_csv(users_data)

    # Only proceed if we have content (CSV header + rows or just header if no users match filter)
    if csv_content:
        # Output to file if specified
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8', newline='') as f: # Specify encoding and newline='' for csv
                    f.write(csv_content)
                logger.info(f"User data successfully written to {args.output}")
            except IOError as e:
                logger.error(f"Error writing to file {args.output}: {e}")
                # Optionally print to stdout as fallback if file write fails
                print("\n--- CSV Output (due to file write error) ---")
                print(csv_content)
                print("--- End CSV Output ---")
            except Exception as e:
                 logger.error(f"An unexpected error occurred writing to file {args.output}: {e}")
                 print("\n--- CSV Output (due to file write error) ---")
                 print(csv_content)
                 print("--- End CSV Output ---")

        else:
            # Always print to stdout if no output file specified
            print(csv_content)
            logger.info("CSV output printed to standard output.")
    else:
        # This case handles API errors or situations where filtering results in zero users
        if not users_data.get("error"):
             logger.info("No users matched the specified criteria (or the organization is empty). No CSV generated.")
        # Error message for API failure already logged earlier

if __name__ == "__main__":
    main()