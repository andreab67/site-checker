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

Run it with a `.env` file (see [configuration.md](configuration.md) for variables). Publish the GUI port on localhost only, and mount a volume if you want GUI saves to survive restarts:

```bash
docker volume create site-checker-data
docker run --rm --env-file .env \
  -e SETTINGS_FILE=/data/settings.json -v site-checker-data:/data \
  -p 127.0.0.1:8080:8080 site-checker:local
```

Open <http://127.0.0.1:8080/> for the heartbeat, `/admin` for the status board, and `/admin/settings` to change URLs and recipients. The image has a `HEALTHCHECK` against `/healthz`, so `docker ps` shows `unhealthy` if the monitor loop stalls.

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
          ports:
            - name: http
              containerPort: 8080
          env:
            - name: SETTINGS_FILE
              value: /data/settings.json
          envFrom:
            - secretRef:
                name: site-checker
          readinessProbe:
            httpGet: { path: /healthz, port: http }
            periodSeconds: 30
          livenessProbe:
            # /healthz fails when the monitor loop stops iterating, not just
            # when the web thread is down.
            httpGet: { path: /healthz, port: http }
            initialDelaySeconds: 60
            periodSeconds: 60
            timeoutSeconds: 5
            failureThreshold: 3
          securityContext:
            runAsNonRoot: true
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          volumeMounts:
            - { name: data, mountPath: /data }
            - { name: tmp, mountPath: /tmp }
          resources:
            requests: { cpu: "50m",  memory: "96Mi" }
            limits:   { cpu: "200m", memory: "192Mi" }
      securityContext:
        fsGroup: 10001
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: site-checker-data
        - name: tmp
          emptyDir: {}
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: site-checker-data
spec:
  accessModes: ["ReadWriteOnce"]
  resources:
    requests:
      storage: 16Mi
---
apiVersion: v1
kind: Service
metadata:
  name: site-checker
spec:
  selector: { app: site-checker }
  ports:
    - name: http
      port: 80
      targetPort: http
```

Apply with `kubectl apply -f deployment.yaml`. Keep `replicas: 1`: every replica polls and emails on its own, and the settings file is single-writer.

Put `SITE_CHECKER_ADMIN_TOKEN` in the same Secret as the SMTP credentials. To reach the GUI without exposing it, run `kubectl port-forward svc/site-checker 8080:80` and open <http://127.0.0.1:8080/>. If you publish it through an Ingress or Gateway, put authentication in front of it (for example oauth2-proxy or your ingress controller's basic-auth) and terminate TLS there. The admin token is a shared secret in a header, not a login system.

Without the PVC (and `SETTINGS_FILE`), GUI saves still work but are lost when the pod restarts.

### FluxCD

If you manage cluster state with [FluxCD](https://fluxcd.io/flux/installation/bootstrap/github/), add the manifest above to your cluster-config repo under a `Kustomization` that points at the directory containing it. Flux will reconcile the `Deployment` on every push.

## 3. Managed container platforms

The container is a single always-on workload (stateless unless you enable `SETTINGS_FILE`), so any "keep one replica running" platform works. The knobs below are the ones you actually need to set.

| Platform | Service | Key settings |
| -------- | ------- | ------------ |
| AWS      | [Fargate](https://aws.amazon.com/fargate/)                           | Task definition with `desiredCount=1`, env vars from Secrets Manager, `awslogs` log driver. Container health check on `/healthz`. For persistent GUI saves, mount EFS and set `SETTINGS_FILE`. |
| Azure    | [Container Apps](https://azure.microsoft.com/en-us/products/container-apps) | `minReplicas=1`, `maxReplicas=1`, secrets bound to env vars, target port `8080`, liveness probe on `/healthz`. Scale-to-zero is NOT desired — this workload must stay running. Use an Azure Files mount for `SETTINGS_FILE`. |
| GCP      | [Cloud Run](https://cloud.google.com/run)                            | Deploy as a Service with `min-instances=1`, `max-instances=1`, CPU always allocated, and port `8080`. Require authentication (IAM) on the service rather than exposing the GUI publicly. A Cloud Run *Job* does not fit: the process is a long-running loop. |

## Image registry

The included [`.gitlab-ci.yml`](../.gitlab-ci.yml) builds and pushes with [Kaniko](https://github.com/GoogleContainerTools/kaniko) to the GitLab registry. The GitHub Actions workflow in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) only **builds** the image — wire it up to a registry (GHCR, ECR, ACR, GAR) when you are ready to publish.
