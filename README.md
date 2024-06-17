# site-checker
Container solution to check a web site and send notifications if changes

# the problem

Acquiring a passport for an Italian citizen in Denver involves regularly checking a specific webpage for any updates or changes. This task requires setting up notifications so that when the webpage is altered or updated, you receive an immediate alert. This method ensures that you are always informed of the latest requirements, procedures, and processing times for passport applications without having to manually check the website continuously.

# the technology

# gitlab-ce - running as self hosted with a build agent running on the same instance 

# kaniko-project - https://github.com/GoogleContainerTools/kaniko

## AWS - t3.xlarge  4 cores - 16 ram 
## Azure - .....
## GCP

https://www.python.org/downloads/


# Software to install

## gitlab-ce  -     https://about.gitlab.com/install/
## docker-ce   -    https://docs.docker.com/engine/install/
## gitlab-runner   -   https://docs.gitlab.com/runner/install/

# Kubernetes Cluster 

You can use a hardware install or an hosted solution $$ being the factor
You can also run the container in your own PC


# Number of repositories to create

To build the container you need only one repository the one you are reading


# FluxCD

In case you want to integrate with FluxCD you will need a repository to bootstrap FluxCD.

https://fluxcd.io/flux/installation/bootstrap/github/

Once bootstrapped you will need a kustomize file to syncronyze the repository site-checker and the Kubernetes cluster.


ToDo

Create Terraform, CloudFormation, deployment scripts 
Add Azure and Google Cloud instructions and suggested specs for instances / containers
Create instuctions to deploy in Azure Container Apps and AWWS Fargate
Detail more FluxCD deployment process and provide instrcutions on how to deploy and integrate
