import argparse
import json
import sys

import requests
from azureml.core.authentication import (
    InteractiveLoginAuthentication,
    MsiAuthentication,
    ServicePrincipalAuthentication,
)
from environs import Env


# temporary workaround function until a bug in environs.read_env(...) is fixed
def find_env_in_parent_directories(env_file_name):
    import os
    import re

    parents = re.split(r"[\\/]", os.path.abspath(env_file_name))[:-1]
    depth = len(parents)
    while depth >= 0:
        path_to_check = "/".join(parents[:depth]) + f"/{env_file_name}"
        if os.path.isfile(path_to_check):
            return path_to_check
        depth -= 1


print("Triggering pipeline...")


# --- helper class definitions
# parses a dictionary argument
class ParseDict(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        d = {}
        if values:
            for item in values:
                split_items = item.split("=", 1)
                key = split_items[0].strip()
                value = split_items[1]
                d[key] = value
        setattr(namespace, self.dest, d)


# --- initialization
print("Initialization...")
parser = argparse.ArgumentParser(allow_abbrev=False)
parser.add_argument("--endpoint", type=str, required=True, help="pipeline endpoint")
parser.add_argument(
    "--parameter_assignments", metavar="KEY=VALUE", nargs="+", action=ParseDict,
)
parser.add_argument(
    "--auth_type",
    choices=["interactive", "service_principal", "msi"],
    required=True,
    help="Specifies the method to authenticate against AzureML Services.",
)
parser.add_argument(
    "--tenant_id", type=str, required=False, help="AAD tenant ID, only needed if service principal auth is used",
)
parser.add_argument(
    "--service_principal_id",
    type=str,
    required=False,
    help="ID of the service principal triggering, only needed if service principal auth is used",
)
parser.add_argument(
    "--service_principal_secret",
    type=str,
    required=False,
    help="Service principal secret, only needed if service principal auth is used. In production scenarios, "
    "you should NOT use this option and pass the secret through an environment variable.",
)
args = parser.parse_args()
endpoint = args.endpoint
parameter_assignments = args.parameter_assignments
auth_type = args.auth_type


# --- send a request to trigger the pipeline
print("Sending request...")
if parameter_assignments:
    print(f"Parameter Assignments:\n{json.dumps(parameter_assignments, indent=2)}")
auth = None
if auth_type == "interactive":
    auth = InteractiveLoginAuthentication()
if auth_type == "service_principal":
    env = Env()
    env.read_env(find_env_in_parent_directories("foundation.env"))
    env.read_env(find_env_in_parent_directories("service-principals.env"))
    tenant_id = args.tenant_id if args.tenant_id else env("TRIGGER_AML_PIPELINE_SP_TENANT_ID")
    service_principal_id = (
        args.service_principal_id if args.service_principal_id else env("TRIGGER_AML_PIPELINE_SP_APP_ID")
    )
    service_principal_secret = (
        args.service_principal_secret if args.service_principal_secret else env("TRIGGER_AML_PIPELINE_SP_SECRET")
    )
    auth = ServicePrincipalAuthentication(
        tenant_id=tenant_id,
        service_principal_id=service_principal_id,
        service_principal_password=service_principal_secret,
    )
if auth_type == "msi":
    auth = MsiAuthentication()

aad_token = auth.get_authentication_header()
trigger_pipeline_response = requests.post(endpoint, headers=aad_token, json={"ParameterAssignments": {}},)
print(f"\nResponse Status Code:\n{trigger_pipeline_response.status_code}")
print(f"\nResponse Body:\n{json.dumps(trigger_pipeline_response.json(), indent=2)}")
print(f"\nPipeline triggered successfully.")

# --- done
print("Done.")

# --- exit with appropriate exit code
is_error = trigger_pipeline_response.status_code != 200
if is_error:
    sys.exit(1)
else:
    sys.exit(0)
