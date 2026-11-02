# 0013 one chart, every install path

status: accepted

The Helm chart in deploy/helm/veto is the only hand-written install source.
deploy/install.yaml is rendered from it (make manifests) for kubectl apply, and the Kustomize base is that file.
Argo CD, Flux and Terraform install the chart itself. CI fails when install.yaml and the chart drift.
Keys never go in values that reach git: the chart reads an existing secret, and creating one from values is for quick tests.

Why: teams install with whatever they already use, and two hand-kept copies drift.
Cost: changing install.yaml by hand is lost on the next render.
