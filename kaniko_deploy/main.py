import base64
import json
import subprocess
import sys
import time
import click
import os
import getpass
from pathlib import Path
from kubernetes import client, config
import yaml
import inspect

config.load_kube_config()
kube_v1 = client.CoreV1Api()
kube_job_v1 = client.BatchV1Api()

KANIKO_BUILD_FILENAE = "kaniko-build.yaml"
AVAILABLE_CMDS = ["deploy"]
DEFAULT_PVC_STORAGE = 5
DEFAULT_PV_CAP = 5


def get_ln():
    return inspect.currentframe().f_lineno


class ManifestConfigs:

    def __init__(self, context_dir: str, read_manifest: bool) -> None:
        self.volume_mount_manifest = "volume.yaml"
        self.volume_claim_mount_manifest = "volume-claim.yaml"
        self.pod_manifest = "pod-kaniko.yaml"
        self.volume_mount_configs = None
        self.volume_claim_mount_configs = None
        self.pod_configs = None
        self.read_manifest = read_manifest
        self._load_configs()
        self.context_dir = context_dir
        self.host_path = "/workspace"
        self.volume_name = None
        self.volume_claim_name = None
        self.pod_name = None

        # if context_dir.startswith("dir") or context_dir.startswith("/") or context_dir.startswith("."):
        #     self.host_path = context_dir

    def _load_configs(self):
        current_directory = os.getcwd()
        vm_manifest = os.path.join(current_directory, self.volume_mount_manifest)
        if os.path.isfile(vm_manifest):
            # print(f"The file '{self.volume_mount_manifest}' exists. Reading the file...")
            with open(vm_manifest, "r") as file:
                self.volume_mount_configs = yaml.safe_load(file)
        elif self.read_manifest:
            print(f"{self.volume_mount_manifest} file not found.")
            raise Exception()

        vcm_manifest = os.path.join(current_directory, self.volume_claim_mount_manifest)
        if os.path.isfile(vcm_manifest):
            with open(vcm_manifest, "r") as file:
                self.volume_claim_mount_configs = yaml.safe_load(file)
        elif self.read_manifest:
            print(f"{self.volume_claim_mount_manifest} file not found.")
            raise Exception()

        pod_manifest = os.path.join(current_directory, self.pod_manifest)
        if os.path.isfile(pod_manifest):
            with open(pod_manifest, "r") as file:
                self.pod_configs = yaml.safe_load(file)
                self.pod_name = self.pod_configs["metadata"]["name"]
        # elif self.read_manifest:
        #     print(f'{self.pod_manifest} file not found.')
        #     raise Exception()

    def get_volume_name(self):
        if self.volume_name:
            return self.volume_name
        elif self.volume_mount_configs:
            self.volume_name = self.volume_mount_configs["metadata"]["name"]
        else:
            self.volume_name = f"workspace-vol--{str(time.time())[:-8]}"
        return self.volume_name

    def get_volume_claim_name(self):
        if self.volume_claim_name:
            return self.volume_claim_name
        elif self.volume_claim_mount_configs:
            self.volume_claim_name = self.volume_claim_mount_configs["metadata"]["name"]
        else:
            self.volume_claim_name = f"workspace-vol-claim--{str(time.time())[:-8]}"
        return self.volume_claim_name

    def get_pod_name(self):
        if self.pod_name:
            return self.pod_name
        elif self.pod_configs:
            self.pod_name = self.pod_configs["metadata"]["name"]
        else:
            self.pod_name = f"kaniko-pod-{str(time.time())[:-8]}"
        return self.pod_name

    def _vmc(self):
        return self.volume_mount_configs if self.volume_mount_configs else None

    def get_pv(self, cap_size:int):
        cap_size = f"{str(cap_size)}Gi"
        pv = client.V1PersistentVolume(
            api_version=self._vmc()["apiVersion"] if self._vmc() else "v1",
            kind=self._vmc()["kind"] if self._vmc() else "PersistentVolume",
            metadata=client.V1ObjectMeta(
                name=(
                    self._vmc()["metadata"]["name"]
                    if self._vmc()
                    else self.get_volume_name()
                ),
                labels={"type": "local"},
            ),
            spec=client.V1PersistentVolumeSpec(
                capacity={
                    "storage": (
                        self._vmc()["spec"]["capacity"]["storage"]
                        if self._vmc()
                        else "5Gi"
                    )
                },
                access_modes=[
                    (
                        self._vmc()["spec"]["accessModes"]
                        if self._vmc()
                        else "ReadWriteOnce"
                    )
                ],
                persistent_volume_reclaim_policy="Retain",
                storage_class_name=(
                    self._vmc()["spec"]["storageClassName"]
                    if self._vmc()
                    else "local-storage"
                ),
                host_path=client.V1HostPathVolumeSource(
                    path=(
                        self._vmc()["spec"]["hostPath"]["path"]
                        if self._vmc()
                        else self.host_path
                    )
                ),
            ),
        )
        return pv

    def _vcmc(self):
        return (
            self.volume_claim_mount_configs if self.volume_claim_mount_configs else None
        )

    def get_pvc(self, cap_size: int):
        storage = f"{str(cap_size)}Gi"
        pvc = client.V1PersistentVolumeClaim(
            api_version=self._vcmc()["apiVersion"] if self._vcmc() else "v1",
            kind=self._vcmc()["kind"] if self._vcmc() else "PersistentVolumeClaim",
            metadata=client.V1ObjectMeta(
                name=(
                    self._vcmc()["metadata"]["name"]
                    if self._vcmc()
                    else self.get_volume_claim_name()
                )
            ),
            spec=client.V1PersistentVolumeClaimSpec(
                access_modes=[
                    (
                        self._vcmc()["spec"]["accessModes"]
                        if self._vcmc()
                        else "ReadWriteOnce"
                    )
                ],
                resources=client.V1ResourceRequirements(
                    requests={
                        "storage": (
                            self._vcmc()["spec"]["resources"]["requests"]["storage"]
                            if self._vcmc()
                            else "5Gi"
                        )
                    }
                ),
                storage_class_name=(
                    self._vcmc()["spec"]["storageClassName"]
                    if self._vcmc()
                    else "local-storage"
                ),
            ),
        )
        return pvc

    # this function can be created later on
    # def get_pod():
    #     pod = client.V1Pod(
    #         api_version="v1",
    #         kind="Pod",
    #         metadata=client.V1ObjectMeta(name=f'kaniko-pod-{str(time.time())[:-8]}'),
    #         spec=client.V1PodSpec(
    #             containers=[
    #                 client.V1Container(
    #                     name=f"kaniko-cont-{str(time.time())[:-8]}",
    #                     image="gcr.io/kaniko-project/executor:latest",
    #                     args=[
    #                         f"--context={self.context_dir}",
    #                         f"--dockerfile={self.docker_filepath}",
    #                         f'{"--no-push" if self.no_push else ("--destination="+self.docker_username+'/'+self.docker_repo)}',
    #                     ],
    #                     volume_mounts=volume_mount_list,
    #                 )
    #             ],
    #             restart_policy="Never",
    #             volumes=volume_list,
    #         )
    #     )
    #     return pod


class KanikoBuild:

    def __init__(
        self,
        context_dir=None,
        docker_filepath=None,
        no_push=False,
        docker_username=None,
        docker_repo=None,
        docker_email=None,
        read_manifest=False,
        pod_name=None,
        pvc_storage=DEFAULT_PVC_STORAGE,
        pv_cap=DEFAULT_PV_CAP,
        wait_for_pod=False,
        pod_delete=False
    ):
        self.context_dir = context_dir
        self.docker_filepath = docker_filepath
        self.docker_username = docker_username
        self.docker_repo = docker_repo
        self.docker_email = docker_email
        self.no_push = no_push
        self.pv_flag = False
        self.pvc_flag = False
        self.pod_flag = False
        self.read_manifest = read_manifest
        self.provided_pod_name = pod_name
        self.pvc_storage=pvc_storage,
        self.pv_cap=pv_cap,
        self.wait_for_pod=wait_for_pod,
        self.pod_delete=pod_delete,
        self.manifest_configs = ManifestConfigs(
            context_dir=self.context_dir, read_manifest=self.read_manifest
        )

    def build(self):
        if self.is_ctx_local_dir():
            if self.is_dockerfile_present():
                if self.read_manifest:
                    self.create_volume_v2()
                    time.sleep(2)
                    self.claim_volume_v2()
                    time.sleep(2)
                else:
                    self.create_volume()
                    self.claim_volume()
                
        if self.no_push == False:
            self.create_kube_secret()

        self.create_pod()
        # if self.read_manifest:
        #     self.create_pod_v2()
        # else:
        #     self.create_pod()

        if self.wait_for_pod:
            if self.check_pod_status():
                print("waiting for pod to succeed ...")
                while self.check_pod_status() in ["Pending", "Running"]:
                    time.sleep(2)
                if self.check_pod_status() == "Succeeded":
                    print("pod status succeeded ...")
                else:
                    print(f'Status of pod : {self.check_pod_status()}')
                    # self.get_pod_logs()

        self.close_gracefully()

    def is_ctx_local_dir(self):
        if Path(self.context_dir).exists():
            return True
        return False

    def is_dockerfile_present(self):
        docker_filepath = self.context_dir + "/" + self.docker_filepath
        if os.path.exists(docker_filepath) == False:
            raise FileNotFoundError(f"No such dockerfile found : '{docker_filepath}'")
        return True

    def create_volume_v2(self):
        cmd = ["kubectl", "apply", "-f", "volume.yaml"]
        res = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        res.wait()
        exit_code = res.returncode
        print(res.stdout.read())
        if exit_code != 0:
            print("something went wrong while creating volume, exiting ...")
            return
        self.pv_flag = True

    def create_volume(self, cap_size=None, volume_name=None):
        print("creating persistent volume ...")
        self.created_vol_cap_size = cap_size
        self.pv_name = "some-pv-name"

        if volume_name == None:
            self.created_vol_name = "dockerfile"  # or you might consider to take input or generate some random
        if cap_size == None:
            self.created_vol_cap_size = "5"  # in Gi consider to take input

        # pv = client.V1PersistentVolume(
        #     api_version="v1",
        #     kind="PersistentVolume",
        #     metadata=client.V1ObjectMeta(name=f'{self.pv_name}-{str(time.time())[:-8]}', labels={"type": "local"}),
        #     spec=client.V1PersistentVolumeSpec(
        #         capacity={"storage": f"{self.created_vol_cap_size}Gi"},
        #         access_modes=["ReadWriteOnce"],
        #         persistent_volume_reclaim_policy="Retain",
        #         host_path=client.V1HostPathVolumeSource(path=self.context_dir),
        #     ),
        # )
        pv = self.manifest_configs.get_pv(self.pv_cap)
        try:
            resp = kube_v1.create_persistent_volume(pv)
            # print(resp)
            self.pv_flag = True
            print("\nPersistent Volume created successfully.")
        except client.exceptions.ApiException as e:
            print("Exception when creating persistent volume : %s\n" % e)

    def claim_volume_v2(self):
        cmd = ["kubectl", "apply", "-f", "volume-claim.yaml"]
        res = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        res.wait()
        exit_code = res.returncode
        print(res.stdout.read())
        if exit_code != 0:
            print("something went wrong while creating volume claim, exiting ...")
            return
        self.pvc_flag = True

    def claim_volume(self, volume_name: str = None, cap_size=None):
        print("creating persistent volume claim ...")
        self.pvc_name = "some-pvc-claim"
        # pvc = client.V1PersistentVolumeClaim(
        #     api_version="v1",
        #     kind="PersistentVolumeClaim",
        #     metadata=client.V1ObjectMeta(name=f'{self.pvc_name}-{str(time.time())[:-8]}'),
        #     spec=client.V1PersistentVolumeClaimSpec(
        #         access_modes=["ReadWriteOnce"],
        #         resources=client.V1ResourceRequirements(requests={"storage": "1Gi"}),
        #     ),
        # )
        pvc = self.manifest_configs.get_pvc(self.pvc_storage)
        try:
            kube_v1.create_namespaced_persistent_volume_claim(
                namespace="default", body=pvc
            )
            self.pvc_flag = True
            print("Persistent Volume Claim created successfully.\n")
        except client.exceptions.ApiException as e:
            print("Exception when creating persistent volume claim : %s\n" % e)

    def create_kube_secret(self):
        secrets = kube_v1.list_namespaced_secret(namespace="default").items
        for secret in secrets:
            if secret.metadata.name == "docker-registry-secret":
                print("docker secret already exists ... skipping adding secrets")
                return
        if self.no_push == False and self.read_manifest == False:
            if self.docker_email == None:
                self.docker_email = input("Enter docker email : ")
            if self.docker_username == None:
                self.docker_username = input("Enter docker username : ")
        self.docker_pass = getpass.getpass("Enter docker password : ")
        print("creating kube secret ...")
        # Define your Docker registry credentials
        docker_config_json = {
            "auths": {
                "https://index.docker.io/v1/": {  # Docker Hub URL
                    "username": f"{self.docker_username}",
                    "password": f"{self.docker_pass}",
                    "email": f"{self.docker_email}",
                }
            }
        }
        # Encode the Docker config JSON to base64
        encoded_docker_config = base64.b64encode(
            json.dumps(docker_config_json).encode()
        ).decode()
        # Create a V1Secret object for Docker registry
        secret = client.V1Secret(
            api_version="v1",
            kind="Secret",
            metadata=client.V1ObjectMeta(
                name="docker-registry-secret", namespace="default"
            ),  # Adjust the namespace as needed
            data={".dockerconfigjson": encoded_docker_config},
            type="kubernetes.io/dockerconfigjson",
        )
        try:
            api_response = kube_v1.create_namespaced_secret(
                namespace="default", body=secret
            )
            print("Secret created. Status='%s'\n" % str(api_response))
            print(api_response)
        except client.exceptions.ApiException as e:
            print("Exception when creating secret: %s\n" % e)

    def create_job(self):
        print("creating job ...")
        # Define the Job spec
        self.vol_secret_name = "docker-secret"
        volume_mount_list = [
            client.V1VolumeMount(
                name="docker-registry-secret", mount_path="/kaniko/.docker"
            )
        ]
        volume_list = [
            client.V1Volume(
                name="docker-registry-secret",
                secret=client.V1SecretVolumeSource(
                    secret_name=self.vol_secret_name,
                    items=[
                        client.V1KeyToPath(key=".dockerconfigjson", path="config.json")
                    ],
                ),
            )
        ]
        if self.pvc_flag:
            volume_mount_list.append(
                client.V1VolumeMount(name="dockerfile-storage", mount_path="/workspace")
            )
            volume_list.append(
                client.V1Volume(
                    name="dockerfile-storage",
                    persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                        claim_name=self.pvc_name
                    ),
                )
            )
        job_spec = client.V1JobSpec(
            template=client.V1JobTemplateSpec(
                metadata=client.V1ObjectMeta(name="some-job"),  # labels={"app": "job"}
                spec=client.V1JobSpec(
                    containers=[
                        client.V1Container(
                            name="kaniko",
                            image="gcr.io/kaniko-project/executor:latest",
                            args=[
                                f"--context={self.context_dir}",
                                f"--dockerfile={self.docker_filepath}",
                                f'{"--no-push" if self.no_push else ("--destination="+self.docker_username+'/'+self.docker_repo)}',
                            ],
                            volume_mounts=volume_mount_list,
                        )
                    ],
                    restart_policy="Never".capitalize,
                    volumes=volume_list,
                ),
            ),
            backoff_limit=3,
        )

        # Define the Job object
        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(name="example-job"),
            spec=job_spec,
        )

        # Create the Job in the specified namespace
        api_instance = client.BatchV1Api()
        try:
            api_response = api_instance.create_namespaced_job(
                namespace="default", body=job
            )
            print(f"Job created. Status='{api_response.status}'\n")
        except client.exceptions.ApiException as e:
            print(f"Exception when creating job: {e}\n")

    def create_pod_v2(self):
        cmd = ["kubectl", "apply", "-f", "pod-kaniko.yaml"]
        res = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        res.wait()
        exit_code = res.returncode
        print(res.stdout.read())
        if exit_code != 0:
            print("something went wrong while creating pod, exiting ...")
            return
        self.pod_flag = True
        return

    def create_pod(self):
        print("creating pod ...")
        self.vol_secret_name = "docker-secret"
        volume_mount_list = [
            client.V1VolumeMount(
                name=self.vol_secret_name, mount_path="/kaniko/.docker"
            )
        ]
        volume_list = [
            client.V1Volume(
                name=self.vol_secret_name,
                secret=client.V1SecretVolumeSource(
                    secret_name="docker-registry-secret",
                    items=[
                        client.V1KeyToPath(key=".dockerconfigjson", path="config.json")
                    ],
                ),
            )
        ]
        if self.pvc_flag:
            volume_mount_list.append(
                client.V1VolumeMount(name="dockerfile-storage", mount_path="/workspace")
            )
            volume_list.append(
                client.V1Volume(
                    name="dockerfile-storage",
                    persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                        claim_name=self.manifest_configs.get_volume_claim_name()
                    ),
                )
            )
        # pod_name = f'kaniko-pod-{str(time.time())[:-8]}'
        pod_name = self.manifest_configs.get_pod_name()
        if self.provided_pod_name:
            pod_name = self.provided_pod_name
        pod = client.V1Pod(
            api_version="v1",
            kind="Pod",
            metadata=client.V1ObjectMeta(name=pod_name),
            spec=client.V1PodSpec(
                containers=[
                    client.V1Container(
                        name=f"kaniko-cont-{str(time.time())[:-8]}",
                        image="gcr.io/kaniko-project/executor:latest",
                        args=[
                            f"--context={self.context_dir}",
                            f"--dockerfile={self.docker_filepath}",
                            f'{"--no-push" if self.no_push else ("--destination="+str(self.docker_username)+'/'+str(self.docker_repo))}',
                        ],
                        volume_mounts=volume_mount_list,
                    )
                ],
                restart_policy="Never",
                volumes=volume_list,
            ),
        )

        try:
            api_response = kube_v1.create_namespaced_pod(namespace="default", body=pod)
            print(f"Pod created. Status='{api_response.status}'\n")
            self.pod_flag = True
        except client.exceptions.ApiException as e:
            print(f"Exception when creating pod: {e}\n")

    def delete_persistent_volume_claim_v2(self):
        volc_name = self.manifest_configs.get_volume_claim_name()
        cmd = ["kubectl", "delete", "pvc", volc_name]
        res = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        res.wait()
        exit_code = res.returncode
        print(res.stdout.read())
        if exit_code != 0:
            print("something went wrong while deleting volume, exiting ...")
            return

    def delete_persistent_volume_v2(self):
        vol_name = self.manifest_configs.get_volume_name()
        cmd = ["kubectl", "delete", "pv", vol_name]
        res = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        res.wait()
        exit_code = res.returncode
        print(res.stdout.read())
        if exit_code != 0:
            print("something went wrong while deleting volume claim, exiting ...")
            return

    def delete_persistent_volume(self):
        try:
            kube_v1.delete_persistent_volume(name=self.pv_name)
            print(f"Persistent Volume '{self.pv_name}' deleted successfully.")
        except client.exceptions.ApiException as e:
            print(f"Exception when deleting Persistent Volume: {e}")

    def delete_persistent_volume_claim(self):
        try:
            kube_v1.delete_persistent_volume(name=self.pvc_name)
            print(f"Persistent Volume Claim'{self.pvc_name}' deleted successfully.")
        except client.exceptions.ApiException as e:
            print(f"Exception when deleting Persistent Volume Claim: {e}")

    def delete_pod_v2(self):
        pod_name = self.manifest_configs.get_pod_name()
        cmd = ["kubectl", "delete", "pod", pod_name]
        res = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        res.wait()
        exit_code = res.returncode
        print(res.stdout.read())
        if exit_code != 0:
            print("something went wrong while deleting pod, exiting ...")
            return

    def check_pod_status(self) -> str:
        time.sleep(2)
        try:
            if self.pod_flag == False:
                return None
            res = kube_v1.read_namespaced_pod_status(
                name=self.manifest_configs.pod_name, namespace="default"
            )
            return res.status.phase
        except client.exceptions.ApiException as e:
            print(f"Exception while checking pod status: {e}")
            return None

    def check_pv_status(self):
        try:
            res = kube_v1.read_persistent_volume_status(
                name=self.manifest_configs.get_volume_name(), namespace="default"
            )
            return res.status.phase
        except client.exceptions.ApiException as e:
            print(f"Exception while checking volume mount status: {e}")
            return None

    def check_pvc_status(self):
        try:
            res = kube_v1.read_namespaced_persistent_volume_claim_status(
                name=self.manifest_configs.get_volume_claim_name(), namespace="default"
            )
            return res.status.phase
        except client.exceptions.ApiException as e:
            print(f"Exception while checking volume claim mount status: {e}")
            return None

    def close_gracefully(self):
        pod_name = self.manifest_configs.get_pod_name()
        if self.provided_pod_name:
            pod_name = self.provided_pod_name
        pods = kube_v1.list_namespaced_pod("default").items
        
        # add try except for the followings
        if self.pod_delete and self.wait_for_pod: 
            for pod in pods:
                if pod.metadata.name == pod_name:
                    kube_v1.delete_namespaced_pod(name=pod_name, namespace="default")
                    break
        elif self.pod_delete:
            if self.check_pod_status() in ['Failed']: # if any wrong in configs, then pod will be failed immediately, close may be consider to delete it
                kube_v1.delete_namespaced_pod(name=pod_name, namespace="default")
                

        vol_claim_name = self.manifest_configs.get_volume_claim_name()
        if self.pvc_flag:
            kube_v1.delete_namespaced_persistent_volume_claim(
                name=vol_claim_name, namespace="default"
            )

        vol_name = self.manifest_configs.get_volume_name()
        if self.pv_flag:
            kube_v1.delete_persistent_volume(name=vol_name)

        # consider to delete secrets also
    def get_pod_logs(self):
        print("getting logs for pod ...")
        pod_name = self.manifest_configs.get_pod_name()
        if self.provided_pod_name:
            pod_name = self.provided_pod_name
        cmd = ["kubectl", "logs", "-f", pod_name]
        res = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        res.wait()
        exit_code = res.returncode
        print(res.stdout.read())
        if exit_code != 0:
            print("something went wrong while getting logs of pod ...")
            return


@click.command()
@click.argument("cmd")
@click.option(
    "--context_dir",
    type=str,
    default=None,
    help="this is directory to you workspace, it can be either local repo, remote",
)
@click.option(
    "--docker_filepath",
    type=str,
    default="Dockerfile",
    help="filename of Dockerfile, like dockerfile or Dockerfile",
)
@click.option(
    "--no_push",
    is_flag=True,
    type=bool,
    default=False,
    help="if you dont want to push to dockerhub, use this flag",
)
@click.option(
    "--docker_username", type=str, default=None, help="provide docker username"
)
@click.option(
    "--docker_email", type=str, default=None, help="provide email id used in docker hub"
)
@click.option(
    "--docker_repo",
    type=str,
    default=None,
    help="provide docker repo where you want to push image",
)
@click.option(
    "--read_manifest",
    is_flag=True,
    type=bool,
    default=False,
    help="use this if you have file volume.yaml and volume-claim.yaml in current directory",
)
@click.option(
    "--pod_name",
    default=None,
    type=str,
    help="option to provide the pod name else it will consider kaniko-pod-<time-stamp>",
)
@click.option(
    "--pvc_storage",
    default=None,
    type=int,
    help="option to provide persistent-volume claim storage value in Gi, Default is 5",
)
@click.option(
    "--pv_cap",
    default=None,
    type=int,
    help="option to provide persistent-volume capacity storage value in Gi, Default is 5",
)
@click.option(
    "--wait_for_pod",
    default=False,
    is_flag=True,
    help="using this flag, will make the script wait till the pod gets out of running status, else it just send the request to create a pod and then end",
)
@click.option(
    "--pod_delete",
    default=False,
    is_flag=True,
    help="using this flag will delete the pod (better be used with --wait_for_pod)",
)
def main(
    cmd,
    context_dir,
    docker_filepath,
    no_push,
    docker_username,
    docker_repo,
    docker_email=None,
    read_manifest=False,
    pod_name=None,
    pvc_storage=None,
    pv_cap=None,
    wait_for_pod=False,
    pod_delete=False
):
    if cmd not in AVAILABLE_CMDS:
        print("No such commands found.\n")
        return
    if cmd != "deploy":
        return

    if read_manifest == False:
        if pvc_storage == None:
            pvc_storage = DEFAULT_PVC_STORAGE
        if pv_cap == None:
            pv_cap = DEFAULT_PV_CAP

    kaniko_build = KanikoBuild(
        context_dir,
        docker_filepath,
        no_push,
        docker_username,
        docker_repo,
        docker_email,
        read_manifest,
        pod_name,
        pvc_storage,
        pv_cap,
        wait_for_pod,
        pod_delete,
    )

    if Path(KANIKO_BUILD_FILENAE).exists():
        Path(KANIKO_BUILD_FILENAE).unlink()

    kaniko_build.build()
    sys.exit(0)


if __name__ == "__main__":
    main()
