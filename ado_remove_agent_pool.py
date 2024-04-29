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

class BadCredentialException(Exception):
    pass
# /class

def _get_agent_pool_id(str_pool_name: str) -> (int):
    dict_params = dict_global_params.copy()
    dict_params['poolName'] = str_pool_name
    # dict_params['per_page'] = per_page
    # dict_params['page'] = page

    # https://dev.azure.com/{organization}/_apis/distributedtask/pools?api-version=7.0
    res = requests.get(f'https://dev.azure.com/{str_ado_org}/_apis/distributedtask/pools',
                       verify=bool_ssl_verify,
                       headers=dict_global_headers,
                       params=dict_params,
                       auth=dict_global_basic_auth)
    logger.debug(f'pool_name="{str_pool_name}",res.status_code={res.status_code}')

    if res.status_code == 203:
        logger.error(f'provided token rejected')
        return False
    # /fi

    if res.status_code == 401:
        logger.error(f'unauthorized access to "{str_ado_org}"')
        return False
    # /fi

    if res.status_code == 404:
        logger.error(f'agent pool "{str_pool_name}" cannot be found in org "{str_ado_org}"')
        return False
    # /fi

    if res.status_code != 200:
        logger.error(f'something went wrong; check the res.status_code')
        return 0
    # /fi

    dict_data = json.loads(res.text)
    if dict_data['count'] == 0:
        logger.info(f'pool_name="{str_pool_name}" NOT found')
        return 0
    # /fi

    for dict_agent in dict_data['value']:
        int_id = int(dict_agent['id'])
        logger.info(f'pool_name="{str_pool_name}" found with id={int_id}')
        return int_id
    # /for

    return 0
# /def

def _delete_agent_pool_id(str_pool_name: str, int_pool_id: int) -> (bool):
    dict_params = dict_global_params.copy()
    dict_params['poolId'] = int_pool_id

    # https://dev.azure.com/{organization}/_apis/distributedtask/pools?api-version=7.0
    res = requests.delete(f'https://dev.azure.com/{str_ado_org}/_apis/distributedtask/pools',
                          verify=bool_ssl_verify,
                          headers=dict_global_headers,
                          params=dict_params,
                          auth=dict_global_basic_auth)
    logger.debug(f'pool_id="{int_pool_id}",res.status_code={res.status_code}')

    if res.status_code == 203:
        logger.error(f'rejected provided token')
        return False
    # /fi

    if res.status_code == 401:
        logger.error(f'unauthorized access to "{str_ado_org}"')
        return False
    # /fi

    if res.status_code != 204:
        logger.error(res.text)
        return False
    # /fi

    logger.info(f'pool_name="{str_pool_name}",pool_id="{int_pool_id}" deleted successfully')
    return True
# /def


def delete_agent_pool_name(str_pool_name: str):
    int_pool_id = _get_agent_pool_id(str_pool_name)
    if int_pool_id:
        _delete_agent_pool_id(str_pool_name, int_pool_id)
    # /if
# /def

# ----------------------------------------------------------------------------------------------------------------------

def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Remove an ADO agent pool (environments ADO_TOKEN and ADO_ORG must be set)'
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

    parser.add_argument('pool_names', nargs='+')

    args = parser.parse_args()
    return args
# /def

# ----------------------------------------------------------------------------------------------------------------------

if __name__ == '__main__':
    # parse arguments passed
    args = parse_args()

    int_verbosity = args.verbosity
    list_pool_names = args.pool_names

    logger = logging.getLogger(__name__)
    c_handler = logging.StreamHandler()
    c_handler.setFormatter(logging.Formatter('%(funcName)s:%(levelname)s:%(message)s'))
    logger.addHandler(c_handler)

    # set logging verbosity
    logger.setLevel(int_verbosity)

    logger.debug(f'verbosity "level"="{logging.getLevelName(int_verbosity)}"')
    logger.debug(f'pool_names="{list_pool_names}"')

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

    for str_pool_name in set(list_pool_names):
        delete_agent_pool_name(str_pool_name)
    # /for
# /if
