import requests
import json
import os
import sys
import argparse
import logging

from requests.auth import HTTPBasicAuth
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# ----------------------------------------------------------------------------------------------------------------------

# get token and org from env variables

str_ado_token = os.getenv('ADO_TOKEN')
# export ADO_TOKEN=xyz

str_ado_org = os.getenv('ADO_ORG')
# export ADO_ORG=my-org

# str_default_ado_org = 'My-Org'  # default ADO Org

# enable SSL vertificate verification
bool_ssl_verify = False

dict_global_basic_auth = HTTPBasicAuth('', str_ado_token)

dict_global_headers = {
    # 'Accept': 'application/vnd.github+json',
}

# default global parameters
dict_global_params = dict()
dict_global_params['api-version'] = '7.1-preview.1'

# ----------------------------------------------------------------------------------------------------------------------

def get_all_projects() -> str:
    list_projects = _get_all_projects()
    str_projects = _get_project_names(list_projects)
    return str_projects
#/def

def _get_all_projects() -> (list):
    dict_params = dict_global_params.copy()

    str_rest_url = f'https://dev.azure.com/{str_ado_org}/_apis/projects'
    logger.debug(f'action="get",rest_url="{str_rest_url}"')

    res = requests.get(str_rest_url,
                       verify=bool_ssl_verify,
                       headers=dict_global_headers,
                       params=dict_params,
                       auth=dict_global_basic_auth)
    logger.debug(f'res.status_code={res.status_code}')

    if res.status_code == 203:
        logger.error(f'rejected token')
        return []
    # /fi

    if res.status_code == 401:
        logger.error(f'unauthorized access to "{str_ado_org}"')
        return []
    # /fi

    if res.status_code != 200:
        logger.error(f'something went wrong; check the res.status_code')
        return []
    # /fi

    dict_data = json.loads(res.text)
    list_projects = dict_data['value']
    return list_projects
# /def

def _get_project_names(list_projects: list) -> (str):
    str_projects = ''
    for project in list_projects:
        str_projects += f'{project["name"]}\n'
    # /for
    return str_projects.strip()
# /def

# ----------------------------------------------------------------------------------------------------------------------

def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='List all ADO projects (environments ADO_TOKEN and ADO_ORG must be set)'
    )

    parser.add_argument(
        '--debug',
        help='Display "debugging" in output (defaults to "info")',
        action='store_const', dest='verbosity',
        const=logging.DEBUG, default=logging.INFO,
    )

    parser.add_argument(
        '--error-only',
        help='Display "error" in output only (filters "info")',
        action='store_const', dest='verbosity',
        const=logging.ERROR,
    )

    args = parser.parse_args()
    return args
# /def

# ----------------------------------------------------------------------------------------------------------------------

if __name__ == '__main__':
    # parse arguments passed
    args = parse_args()

    int_verbosity = args.verbosity

    logger = logging.getLogger(__name__)
    c_handler = logging.StreamHandler()
    c_handler.setFormatter(logging.Formatter('%(funcName)s:%(levelname)s:%(message)s'))
    logger.addHandler(c_handler)

    # set logging verbosity
    logger.setLevel(int_verbosity)

    logger.debug(f'verbosity "level"="{logging.getLevelName(int_verbosity)}"')
    if not str_ado_token:
        logger.error('environment variable "ADO_TOKEN" is not set or empty.')
        sys.exit(1)
    # /if

    if not str_ado_org:
        # str_ado_org = str_default_ado_org
        logger.error('environment variable "ADO_ORG" is not set or empty.')
        sys.exit(1)
    # /if

    logger.debug(f'org="{str_ado_org}"')

    str_projects = get_all_projects()
    print(str_projects)
    # /if
# /if
