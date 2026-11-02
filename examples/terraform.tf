# example, not tested in this repo: the terraform helm provider installs the chart from the oci registry
resource "helm_release" "veto" {
  name             = "veto"
  namespace        = "veto"
  create_namespace = true
  repository       = "oci://ghcr.io/prashant-zo/charts"
  chart            = "veto"
  version          = "0.1.0"

  values = [yamlencode({
    model    = { existingSecret = "veto-model" }
    evidence = { githubRepo = "your-org/your-app" }
  })]
}
