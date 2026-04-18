# site-checker

[![CI](https://github.com/andreab67/site-checker/actions/workflows/ci.yml/badge.svg)](https://github.com/andreab67/site-checker/actions/workflows/ci.yml)
[![License: BSD-2-Clause](https://img.shields.io/badge/License-BSD%202--Clause-orange.svg)](LICENSE)

Container solution to check a web site and send an email notification when its content changes.

## The problem

Acquiring a passport for an Italian citizen in Denver involves regularly checking a specific webpage for any updates or changes. This task requires setting up notifications so that when the webpage is altered or updated, you receive an immediate alert. This method ensures that you are always informed of the latest requirements, procedures, and processing times for passport applications without having to manually check the website continuously.

## Technology

- [GitLab CE](https://about.gitlab.com/install/)
- [Kaniko](https://github.com/GoogleContainerTools/kaniko)
- [AWS Fargate](https://aws.amazon.com/fargate/)
- [AWS SES](https://aws.amazon.com/ses/)
- [Azure Container Apps](https://azure.microsoft.com/en-us/products/container-apps)
- [Google Cloud Run](https://cloud.google.com/run?hl=en)
- [Python 3.11](https://www.python.org/downloads/)

## Software to install

- [GitLab CE](https://about.gitlab.com/install/)
- [Docker CE](https://docs.docker.com/engine/install/)
- [GitLab Runner](https://docs.gitlab.com/runner/install/)

## Kubernetes cluster

You can use a hardware install or a hosted solution ($$ being the factor). You can also run the container on your own PC. See [docs/deployment.md](docs/deployment.md) for concrete examples.

## Repositories

To build the container you only need one repository — the one you are reading.

## FluxCD

In case you want to integrate with [FluxCD](https://fluxcd.io/flux/installation/bootstrap/github/) you will need a repository to bootstrap FluxCD. Once bootstrapped you will need a kustomize file to synchronize the `site-checker` repository and the Kubernetes cluster.

## Configuration

All runtime configuration is provided via environment variables. See [docs/configuration.md](docs/configuration.md) for the full reference.

## Deployment

Docker quickstart, Kubernetes manifest example, and notes for Fargate / Container Apps / Cloud Run live in [docs/deployment.md](docs/deployment.md).

## CI

Continuous integration runs on every push and pull request via GitHub Actions — see [`.github/workflows/ci.yml`](.github/workflows/ci.yml). The legacy GitLab pipeline in [`.gitlab-ci.yml`](.gitlab-ci.yml) is retained for GitLab-hosted mirrors.

## Contributing

PRs are welcome. Fork the repo, create a feature branch, and open a pull request — CI must pass before merge. Add your name to [CONTRIBUTORS.md](CONTRIBUTORS.md) in the same PR.

## Changelog

Release notes live in [CHANGELOG.md](CHANGELOG.md) and follow [Keep a Changelog](https://keepachangelog.com/).

## License

This project is licensed under the BSD 2-Clause License — see [LICENSE](LICENSE) for the full text.

## Roadmap

- Terraform modules
- CloudFormation templates
- Deployment scripts
- Azure-specific specs
- GCP-specific specs
- Detailed instructions for Azure Container Apps and AWS Fargate
- Expanded FluxCD deployment walkthrough
