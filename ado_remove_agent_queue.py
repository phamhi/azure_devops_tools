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

def delete_agent_queue_name(str_project_name: str, str_queue_name: str) -> (bool):
    list_projects =_get_all_projects()
    str_project_id = _get_project_id(str_project_name, list_projects)
    logger.debug(f'project id is "{str_project_id}"')

    if not str_project_id:
        logger.error(f'cannot find project "{str_project_name}"')
        return False
    # /if

    int_queue_id = _get_agent_queue_id(str_project_name, str_queue_name)

    if int_queue_id:
        _delete_agent_queue_id(str_project_id, str_pool_name, int_queue_id)
    # /if
    return True
# /def

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
        logger.error(f'something went wrong; check res.status_code')
        return []
    # /fi

    dict_data = json.loads(res.text)
    list_projects = dict_data['value']
    return list_projects
# /def

def _get_project_id(str_project_name: str, list_projects: list) -> (str):
    for dict_project in list_projects:
        logger.debug(f'comparing "{dict_project["name"].lower()}" against "{str_project_name.lower()}"')
        if dict_project['name'].lower() == str_project_name.lower():
            str_id = dict_project['id']
            logger.debug(f'found project "{str_project_name}" with id: "{str_id}"')
            return str_id
        # /if
    # /for
    return ""
# /def

def _get_agent_queue_id(str_project_name: str, str_queue_name: str) -> (int):
    dict_params = dict_global_params.copy()
    dict_params['queueNames'] = str_queue_name

    str_rest_url = f'https://dev.azure.com/{str_ado_org}/{str_project_name}/_apis/distributedtask/queues'
    logger.debug(f'action="get",rest_url="{str_rest_url}"')

    res = requests.get(str_rest_url,
                       verify=bool_ssl_verify,
                       headers=dict_global_headers,
                       params=dict_params,
                       auth=dict_global_basic_auth)
    logger.debug(f'queue_name="{str_queue_name}",res.status_code={res.status_code}')

    if res.status_code == 203:
        logger.error(f'rejected token')
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
        logger.error(f'something went wrong; check res.status_code')
        return 0
    # /fi

    dict_data = json.loads(res.text)
    if dict_data['count'] == 0:
        logger.info(f'queue_name="{str_pool_name}" NOT found')
        return 0
    # /fi

    for dict_agent in dict_data['value']:
        int_id = int(dict_agent['id'])
        logger.info(f'queue_name="{str_pool_name}" found with id={int_id}')
        return int_id
    # /for

    return 0
# /def

def _delete_agent_queue_id(str_project_id: str, str_queue_name: str, int_queue_id: int) -> (bool):
    dict_params = dict_global_params.copy()

    str_rest_url = f'https://dev.azure.com/{str_ado_org}/{str_project_id}/_apis/distributedtask/queues/{int_queue_id}'
    logger.debug(f'action="delete",rest_url="{str_rest_url}"')

    res = requests.delete(str_rest_url,
                          verify=bool_ssl_verify,
                          headers=dict_global_headers,
                          params=dict_params,
                          auth=dict_global_basic_auth)
    logger.debug(f'queue_id="{int_queue_id}",res.status_code={res.status_code}')

    if res.status_code == 203:
        logger.error(f'rejected token')
        return False
    # /fi

    if res.status_code == 401:
        logger.error(f'unauthorized access to "{str_ado_org}"')
        return False
    # /fi

    if res.status_code != 204:
        logger.error(f'something went wrong; check res.status_code')
        return False
    # /fi

    logger.info(f'queue_name="{str_queue_name}",queue_id="{int_queue_id}" deleted successfully')
    return True
# /def

# ----------------------------------------------------------------------------------------------------------------------

def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Remove agent queue(s) (environments ADO_TOKEN and ADO_ORG must be set)'
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

    parser.add_argument(
        '-p', '--project',
        required=True,
        help='Use this project name',
        dest='project',
        default='default',
    )

    parser.add_argument('agent_queue_names', nargs='+')

    args = parser.parse_args()
    return args
# /def

def remove_duplicates(list_input:list) -> (list):
    from collections import OrderedDict
    return list(OrderedDict.fromkeys(list_input))
# /def

# ----------------------------------------------------------------------------------------------------------------------

if __name__ == '__main__':
    # parse arguments passed
    args = parse_args()

    int_verbosity = args.verbosity
    str_project = args.project.strip()
    list_agent_queue_names = remove_duplicates(args.agent_queue_names)

    logger = logging.getLogger(__name__)
    c_handler = logging.StreamHandler()
    c_handler.setFormatter(logging.Formatter('%(funcName)s:%(levelname)s:%(message)s'))
    logger.addHandler(c_handler)

    # set logging verbosity
    logger.setLevel(int_verbosity)

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

    logger.debug(f'verbosity "level"="{logging.getLevelName(int_verbosity)}"')
    logger.debug(f'project="{str_project}"')
    logger.debug(f'agent_queue_names="{list_agent_queue_names}"')

    for str_pool_name in list_agent_queue_names:
        delete_agent_queue_name(str_project, str_pool_name)
    # /for
# /if
