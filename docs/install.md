# install

One Helm chart is the source for every way to install Veto. `deploy/install.yaml` is rendered from it
with `make manifests`, and the Kustomize base, Argo CD, Flux and Terraform all use one or the other.

## what your cluster needs

- Argo Rollouts, with your service as a Rollout with canary steps
- Prometheus with OpenTelemetry span metrics (the spanmetrics connector), split by the `rollouts-pod-template-hash` pod label
- Loki with your pod logs, carrying the same label
- image tags that point at a pull request: `pr-<number>-<sha>`

The metric and label names are fixed for now. Reading them from values is next on the [roadmap](roadmap.md).

## 1. the model key

Make a secret first, in the namespace you install into. Never put keys in values files that go to git.

```bash
kubectl create namespace veto
kubectl -n veto create secret generic veto-model --from-literal=VETO_MODEL_API_KEY=<your key>
```

Optional keys in the same secret: `VETO_FALLBACK_API_KEY` (used when `model.fallback.baseUrl` is set)
and `VETO_GITHUB_TOKEN` (raises the GitHub API limit from 60 calls an hour).

## 2. install, pick one

**Helm**

```bash
helm install veto oci://ghcr.io/prashant-zo/charts/veto --version 0.1.0 -n veto \
  --set model.existingSecret=veto-model \
  --set evidence.githubRepo=your-org/your-app \
  --set evidence.prometheusUrl=http://prometheus-server.monitoring.svc:80 \
  --set evidence.lokiUrl=http://loki.monitoring.svc:3100
```

All settings are in [values.yaml](../deploy/helm/veto/values.yaml).

**kubectl apply**

```bash
kubectl apply -f https://github.com/prashant-zo/veto/releases/download/v0.1.0/install.yaml
kubectl -n veto set env deploy/veto VETO_GITHUB_REPO=your-org/your-app
```

**Kustomize**: use `https://github.com/prashant-zo/veto//deploy?ref=v0.1.0` as a base, or copy
[deploy/kustomize/example](../deploy/kustomize/example) and change the urls and the repo.

**Argo CD**: [deploy/examples/argocd-application.yaml](../deploy/examples/argocd-application.yaml)

**Flux**: [deploy/examples/flux-helmrelease.yaml](../deploy/examples/flux-helmrelease.yaml)

**Terraform**: [deploy/examples/terraform.tf](../deploy/examples/terraform.tf)

Helm, kubectl and Kustomize are tested on kind. The Argo CD, Flux and Terraform files are examples.

## 3. gate a rollout

Add an analysis step after the canary has had about two minutes of traffic.
promote continues the rollout, abort aborts it, hold pauses it for a person.

```yaml
strategy:
  canary:
    steps:
      - setWeight: 50
      - pause: {duration: 150s}
      - analysis:
          templates:
            - templateName: veto
              clusterScope: true
          args:
            - name: namespace
              value: shop
            - name: rollout
              value: checkout
```

Decisions show up as Events on the Rollout and in `kubectl -n veto logs deploy/veto`.

## upgrades

Change the chart in `deploy/helm/veto`, run `make manifests`, commit both. CI fails if `install.yaml`
was not rendered again. A tag like `v0.1.0` publishes the image, the chart and the release.
