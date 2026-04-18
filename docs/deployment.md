# Deployment

This guide covers the three supported ways to run `site-checker`:

1. Locally with Docker
2. On a Kubernetes cluster
3. On a managed container platform (AWS Fargate, Azure Container Apps, Google Cloud Run)

All options run the same image built from the [`Dockerfile`](../Dockerfile) in the repo root. See [configuration.md](configuration.md) for the environment variables the image expects.

## 1. Local Docker quickstart

Build the image:

```bash
docker build -t site-checker:local .
```

Run it with a `.env` file (see [configuration.md](configuration.md) for variables):

```bash
docker run --rm --env-file .env site-checker:local
```

Tail logs with `docker logs -f <container>` (the script logs to stderr).

## 2. Kubernetes

Minimal `Deployment` — replace `REGISTRY/IMAGE:TAG` with your pushed image and create the referenced `Secret` first (`kubectl create secret generic site-checker --from-env-file=.env`).

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: site-checker
  labels: { app: site-checker }
spec:
  replicas: 1
  selector:
    matchLabels: { app: site-checker }
  template:
    metadata:
      labels: { app: site-checker }
    spec:
      containers:
        - name: site-checker
          image: REGISTRY/IMAGE:TAG
          envFrom:
            - secretRef:
                name: site-checker
          resources:
            requests: { cpu: "50m",  memory: "64Mi" }
            limits:   { cpu: "200m", memory: "128Mi" }
```

Apply with `kubectl apply -f deployment.yaml`.

### FluxCD

If you manage cluster state with [FluxCD](https://fluxcd.io/flux/installation/bootstrap/github/), add the manifest above to your cluster-config repo under a `Kustomization` that points at the directory containing it. Flux will reconcile the `Deployment` on every push.

## 3. Managed container platforms

The container is stateless and a single always-on workload, so any "keep one replica running" platform works. The knobs below are the ones you actually need to set.

| Platform | Service | Key settings |
| -------- | ------- | ------------ |
| AWS      | [Fargate](https://aws.amazon.com/fargate/)                           | Task definition with `desiredCount=1`, env vars from Secrets Manager, `awslogs` log driver. |
| Azure    | [Container Apps](https://azure.microsoft.com/en-us/products/container-apps) | `minReplicas=1`, `maxReplicas=1`, secrets bound to env vars. Scale-to-zero is NOT desired — this workload must stay running. |
| GCP      | [Cloud Run](https://cloud.google.com/run)                            | Deploy as a **Cloud Run Job** on a schedule, OR as a Service with `min-instances=1` and CPU always allocated. |

## Image registry

The included [`.gitlab-ci.yml`](../.gitlab-ci.yml) builds and pushes with [Kaniko](https://github.com/GoogleContainerTools/kaniko) to the GitLab registry. The GitHub Actions workflow in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) only **builds** the image — wire it up to a registry (GHCR, ECR, ACR, GAR) when you are ready to publish.
