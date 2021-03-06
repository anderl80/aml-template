from azureml.core import Workspace
from azureml.core.compute import AksCompute, AmlCompute, ComputeTarget
from azureml.exceptions import ComputeTargetException
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


# --- configuration
print("Loading configuration...")
env = Env()
env.read_env(find_env_in_parent_directories("foundation.env"))
env.read_env(find_env_in_parent_directories("service-principals.env"))

# - subscription, resource group and workspace
subscription_id = env("SUBSCRIPTION_ID")
resource_group = env("RESOURCE_GROUP")
resource_group_create_if_not_exists = env.bool("RESOURCE_GROUP_CREATE_IF_NOT_EXISTS")
workspace_name = env("WORKSPACE_NAME")
workspace_region = env("WORKSPACE_REGION")
workspace_hbi = env.bool("WORKSPACE_HBI")

# - service principals
# SP for deploying a model as webservice
deploy_model_sp_tenant_id = env("DEPLOY_MODEL_SP_TENANT_ID")
deploy_model_sp_app_id = env("DEPLOY_MODEL_SP_APP_ID")
deploy_model_sp_secret = env("DEPLOY_MODEL_SP_SECRET")

# - clusters
# CPU batch cluster
cpu_batch_cluster_name = env("CPU_BATCH_CLUSTER_NAME")
cpu_batch_cluster_vm_size = env("CPU_BATCH_CLUSTER_VM_SIZE")
cpu_batch_cluster_min_nodes = env.int("CPU_BATCH_CLUSTER_MIN_NODES")
cpu_batch_cluster_max_nodes = env.int("CPU_BATCH_CLUSTER_MAX_NODES")
cpu_batch_cluster_idle_seconds_before_scaledown = env.int(
    "CPU_BATCH_CLUSTER_IDLE_SECONDS_BEFORE_SCALEDOWN"
)
# GPU batch cluster
gpu_batch_cluster_name = env("GPU_BATCH_CLUSTER_NAME")
gpu_batch_cluster_vm_size = env("GPU_BATCH_CLUSTER_VM_SIZE")
gpu_batch_cluster_min_nodes = env.int("GPU_BATCH_CLUSTER_MIN_NODES")
gpu_batch_cluster_max_nodes = env.int("GPU_BATCH_CLUSTER_MAX_NODES")
gpu_batch_cluster_idle_seconds_before_scaledown = env.int(
    "GPU_BATCH_CLUSTER_IDLE_SECONDS_BEFORE_SCALEDOWN"
)
# AKS Cluster
# enabled
aks_cluster_enabled = env.bool("AKS_CLUSTER_ENABLED")
# name, size and region
aks_cluster_name = env("AKS_CLUSTER_NAME")
aks_cluster_region = env("AKS_CLUSTER_REGION")
aks_cluster_agent_count = env.int("AKS_CLUSTER_AGENT_COUNT")
aks_cluster_vm_size = env("AKS_CLUSTER_VM_SIZE")
# SSL/TLS
aks_cluster_use_certificate_from_microsoft = env.bool(
    "AKS_CLUSTER_USE_CERTIFICATE_FROM_MICROSOFT"
)
aks_cluster_leaf_domain_label = env("AKS_CLUSTER_LEAF_DOMAIN_LABEL", None)
# custom certificate
# notes: - no values needed if a certificate from Microsoft is used
#        - the cname in the certificate must match the DNS name of the cluster
#        - be cautious with self-signed certificates, some applications need a real certificate to work properly
aks_cluster_ssl_cname = env("AKS_CLUSTER_SSL_CNAME", None)
aks_cluster_ssl_cert_pem_file = env("AKS_CLUSTER_SSL_CERT_PEM_FILE", None)
aks_cluster_ssl_key_pem_file = env("AKS_CLUSTER_SSL_KEY_PEM_FILE", None)
# VNET
aks_cluster_vnet_resourcegroup_name = env("AKS_CLUSTER_VNET_RESOURCEGROUP_NAME", None)
aks_cluster_vnet_name = env("AKS_CLUSTER_VNET_NAME", None)
aks_cluster_subnet_name = env("AKS_CLUSTER_SUBNET_NAME", None)
aks_cluster_service_cidr = env("AKS_CLUSTER_SERVICE_CIDR", None)
aks_cluster_dns_service_ip = env("AKS_CLUSTER_DNS_SERVICE_IP", None)
aks_cluster_docker_bridge_cidr = env("AKS_CLUSTER_DOCKER_BRIDGE_CIDR", None)
aks_cluster_purpose = env("AKS_CLUSTER_PURPOSE", None)


# --- create resources

# workspace
print("Setting up workspace...")
print(f"Subscription ID : {subscription_id}")
print(f"Resource Group  : {resource_group}")
print(f"Region          : {workspace_region}")
print(f"Workspace Name  : {workspace_name}")
workspace = Workspace.create(
    name=workspace_name,
    subscription_id=subscription_id,
    resource_group=resource_group,
    location=workspace_region,
    create_resource_group=resource_group_create_if_not_exists,
    sku="enterprise",
    hbi_workspace=workspace_hbi,
    exist_ok=True,
    show_output=True,
)

# secrets
print("Updating Key Vault...")
keyvault = workspace.get_default_keyvault()
# note: Key Vault allows only key names that follow the ^[0-9a-zA-Z-]+$ pattern.
#       therefore, we replace the _ chars against -
keyvault.set_secret(name="DEPLOY-MODEL-SP-TENANT-ID", value=deploy_model_sp_tenant_id)
keyvault.set_secret(name="DEPLOY-MODEL-SP-APP-ID", value=deploy_model_sp_app_id)
keyvault.set_secret(name="DEPLOY-MODEL-SP-SECRET", value=deploy_model_sp_secret)

# environment(s)
# TODO: complete as needed

# CPU batch cluster
print("Setting up CPU batch compute cluster...")
try:
    cpu_batch_compute_cluster = ComputeTarget(
        workspace=workspace, name=cpu_batch_cluster_name
    )
    print(f"Cluster '{cpu_batch_cluster_name}' exists already.")
    # TODO: add cluster update (once needed)
except ComputeTargetException:
    print(f"Cluster '{cpu_batch_cluster_name}' does not exist yet.")
    print("Creating cluster...")
    cpu_batch_compute_cluster = ComputeTarget.create(
        workspace,
        cpu_batch_cluster_name,
        AmlCompute.provisioning_configuration(
            vm_size=cpu_batch_cluster_vm_size,
            min_nodes=cpu_batch_cluster_min_nodes,
            max_nodes=cpu_batch_cluster_max_nodes,
            idle_seconds_before_scaledown=cpu_batch_cluster_idle_seconds_before_scaledown,
        ),
    )
    cpu_batch_compute_cluster.wait_for_completion(show_output=True)

# GPU batch cluster
print("Setting up GPU batch compute cluster...")
try:
    gpu_batch_compute_cluster = ComputeTarget(
        workspace=workspace, name=gpu_batch_cluster_name
    )
    print(f"Cluster '{gpu_batch_cluster_name}' exists already.")
    # TODO: add cluster update (once needed)
except ComputeTargetException:
    print(f"Cluster '{gpu_batch_cluster_name}' does not exist yet.")
    print("Creating cluster...")
    gpu_batch_compute_cluster = ComputeTarget.create(
        workspace,
        gpu_batch_cluster_name,
        AmlCompute.provisioning_configuration(
            vm_size=gpu_batch_cluster_vm_size,
            min_nodes=gpu_batch_cluster_min_nodes,
            max_nodes=gpu_batch_cluster_max_nodes,
            idle_seconds_before_scaledown=gpu_batch_cluster_idle_seconds_before_scaledown,
        ),
    )
    gpu_batch_compute_cluster.wait_for_completion(show_output=True)

# AKS cluster
if aks_cluster_enabled:
    print("Setting up AKS cluster...")
    try:
        aks_cluster = ComputeTarget(workspace=workspace, name=aks_cluster_name)
        print(f"Cluster '{aks_cluster_name}' exists already.")
    except ComputeTargetException:
        print(f"Cluster '{aks_cluster_name}' does not exist yet.")
        print("Creating cluster...")
        provisioning_configuration = AksCompute.provisioning_configuration(
            agent_count=aks_cluster_agent_count,
            vm_size=aks_cluster_vm_size,
            ssl_cname=aks_cluster_ssl_cname,
            ssl_cert_pem_file=aks_cluster_ssl_cert_pem_file,
            ssl_key_pem_file=aks_cluster_ssl_key_pem_file,
            location=aks_cluster_region,
            vnet_resourcegroup_name=aks_cluster_vnet_resourcegroup_name,
            vnet_name=aks_cluster_vnet_name,
            subnet_name=aks_cluster_subnet_name,
            service_cidr=aks_cluster_service_cidr,
            dns_service_ip=aks_cluster_dns_service_ip,
            docker_bridge_cidr=aks_cluster_docker_bridge_cidr,
            cluster_purpose=aks_cluster_purpose,
        )

        if aks_cluster_use_certificate_from_microsoft:
            provisioning_configuration.enable_ssl(
                leaf_domain_label=aks_cluster_leaf_domain_label
            )
        else:
            provisioning_configuration.enable_ssl(
                ssl_cert_pem_file=aks_cluster_ssl_cert_pem_file,
                ssl_key_pem_file=aks_cluster_ssl_key_pem_file,
                ssl_cname=aks_cluster_ssl_cname,
            )

        aks_cluster = ComputeTarget.create(
            workspace=workspace,
            name=aks_cluster_name,
            provisioning_configuration=provisioning_configuration,
        )

        aks_cluster.wait_for_completion(show_output=True)

# additional general data store used by all projects
# some_external_blob_datastore_name = env("SOME_EXTERNAL_BLOB_DATASTORE_NAME"]
# some_external_blob_container_name = env("SOME_EXTERNAL_BLOB_CONTAINER_NAME"]
# some_external_blob_account_name = env("SOME_EXTERNAL_BLOB_ACCOUNT_NAME"]
# some_external_blob_account_key = env("SOME_EXTERNAL_BLOB_ACCOUNT_KEY"]
# Datastore.register_azure_blob_container(
#     workspace=workspace,
#     datastore_name=some_external_blob_datastore_name,
#     container_name=some_external_blob_container_name,
#     account_name=some_external_blob_account_name,
#     account_key=some_external_blob_account_key,
# )

print("Done.")
