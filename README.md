
## README.md

# About tool
This tool can be used to create and push a docker image from local or open remote directory to docker hub(can be private).
For local directories, tool will create a persistent-volume, persitent-volume-claim, and kaniko-pod temporary and all will be deleted once the image has been pushed to the docker hub.

# Installation
pip install kaniko_deploy==1.2

# pre-requisites 
Make sure you have connection with kubernetes : 
*for remote kubenetes obtain kubernetes config file and set it's path to env var KUBECONFIG ,(else keep it at respective OS ~/.kube/config path)

For local dirs, the directories should be mounted
if using minikube, then mount using `minikube mount $WORKDIR:/<your-kube-work-dir>`

# steps
    1. For local directories open the terminal wherever your project is (anywhere for remote directories)
    2. either create python3.12 virtual env and then install the kaniko_build(recommended) or can be installed globally also 
    3. you can opt to create volume.yaml, volume-claim.yaml (once for each project) so to provide configs as user's requirements or wish else you by default some values will be taken if not provided by optional flags (like pvc storage, pod name, ..etc)
    4. refer the below mentioned few example commands as per your requirements or you can use --help flag

replace the username, email and docker repo with yours (if docker secrets are not present then password will be asked for first time)

# Exmaple command 
1. for remote directories
`python -m kaniko_deploy deploy --context_dir=git://github.com//Imoustak/kaniko-build-demo.git --docker_filepath=dockerfile --docker_username=<your-docker-username> --docker_email=<your-docker-email> --docker_repo=<your-repo>`

2. Running in you current dir WITH volume.yaml & volume-claim.yaml files
`python -m kaniko_deploy deploy --context_dir=. --docker_filepath=Dockerfile --docker_username=<your-docker-username> --docker_email=<your-docker-email> --docker_repo=<your-repo> --read_manifest`

3.
Running in you current dir WITHOUT volume.yaml & volume-claim.yaml files
`python -m kaniko_deploy deploy --context_dir=. --docker_filepath=Dockerfile --docker_username=<your-docker-username> --docker_email=<your-docker-email> --docker_repo=<your-repo>`


Note:
Currently this is desgined for namespace default only, can be further editted to handle dynamic namespaces
Secret name for docker-registry is considered as "docker-registry-secret" ans it is not deleted after process


# to do 
- add function to get logs if got any errors from k8 while in process
- add caching for kaniko
- add custom exceptions and terminate gracefully
- add functionality for aws or any other cloud volume mount
- check other kaniko flags(or features) to imporve this tool
- write test cases
- logs