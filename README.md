# site-checker
FluxCD Integrated solution to check a web site and send notifications if changes

# the problem

Aquiring a passport for an italian citizen in Denver is a taks that needs something checking a web page for changes and sending an notification when a change happens.

# the technology

gitlab-ce - running as self hosted with a build agent running on the same instance 

AWS - t3.xlarge  4 cores - 16 ram 
Azure - .....

https://www.python.org/downloads/


# Software to install

gitlab-ce  -     https://about.gitlab.com/install/
docker-ce   -    https://docs.docker.com/engine/install/
gitlab-runner   -   https://docs.gitlab.com/runner/install/

# Kubernetes Cluster 

You can use a hardware install or an hosted solution $$ being the factor
You can also run the container in your own PC


# Number of repositories to create

To build the container you need only one repository the one you are reading


# FluxCD

In case you want to integrate with FluxCD you will need a repository to bootstrap FluxCD.

https://fluxcd.io/flux/installation/bootstrap/github/

Once bootstartpped you will need a kustomize file to syncronyze the repository site-checker and the Kubernetes cluster.


ToDo

Create Terraform, CloudFormation, deployment scripts 
Add Azure and Google Cloud instructions and suggested specs for instances / containers
Create instuctions to deploy in Azure Container Apps and AWWS Fargate
