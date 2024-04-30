# azure_devops_tools

## ado_get_all_projects.py

Get and output all of the Azure DevOps projects.

```shell
% python ado_get_all_projects.py --help
usage: ado_get_all_projects.py [-h] [--debug] [--error-only]

List all ADO projects (environments ADO_TOKEN and ADO_ORG must be set)

options:
  -h, --help    show this help message and exit
  --debug       Display "debugging" in output (defaults to "info")
  --error-only  Display "error" in output only (filters "info")
```


```shell
export ADO_TOKEN=mytoken
export ADO_ORG=myorg
```

```shell
python ado_get_all_projects.py
```

Example output
```shell
myproject1
myproject2
```

## ado_get_all_projects.py

Remove Azure DevOps agent queue names.

```shell
% python ado_remove_agent_queue.py --help
usage: ado_remove_agent_queue.py [-h] [--debug] [--error-only] -p PROJECT agent_queue_names [agent_queue_names ...]

Remove agent queue(s) (environments ADO_TOKEN and ADO_ORG must be set)

positional arguments:
  agent_queue_names

options:
  -h, --help            show this help message and exit
  --debug               Display "debugging" in output (defaults to "info")
  --error-only          Display "error" in output only (filters "info")
  -p PROJECT, --project PROJECT
                        Use this project name
```


```shell
export ADO_TOKEN=mytoken
export ADO_ORG=myorg
```

```shell
python ado_remove_agent_queue.py -p spaceship banana apple 
```

Example output
```shell
_get_agent_queue_id:INFO:queue_name="banana" found with id=68
_delete_agent_queue_id:INFO:queue_name="banana",queue_id="68" deleted successfully
_get_agent_queue_id:INFO:queue_name="apple" found with id=67
_delete_agent_queue_id:INFO:queue_name="apple",queue_id="67" deleted successfully
```

## ado_update_agent_queue_permission.py

Update Azure DevOps agent queue's permission.

Personal Access Token (PAT) requires the following permissions:
- Project and Team: **Read**
- Security: **Manage**

```shell
% python ado_update_agent_queue_permission.py --help
usage: ado_update_agent_queue_permission.py [-h] [--debug] [--error-only] -p PROJECT --all-users -r ROLE

Update an agent queue's permission (environments ADO_TOKEN and ADO_ORG must be set)

options:
  -h, --help            show this help message and exit
  --debug               Display "debugging" in output (defaults to "info")
  --error-only          Display "error" in output only (filters "info")
  -p PROJECT, --project PROJECT
                        Use this project name
  --all-users           Target this user(s)
  -r ROLE, --role ROLE  Role to be set (e.g. reader, user creator, administrator)
```


```shell
export ADO_TOKEN=mytoken
export ADO_ORG=myorg
```

```shell
python ado_update_agent_queue_permission.py -p spaceship --all-users -r administrator 
```

Example output
```shell
_put_permission:INFO:successfully updated role to "Administrator" for user "[Spaceship]\Release Administrators"
_put_permission:INFO:successfully updated role to "Administrator" for user "[Spaceship]\Project Administrators"
_put_permission:INFO:successfully updated role to "Administrator" for user "[Spaceship]\Project Valid Users"
_put_permission:INFO:successfully updated role to "Administrator" for user "[Spaceship]\Build Administrators"
<module>:INFO:completed updating permission on project "spaceship"; check the logs for any errors
```
