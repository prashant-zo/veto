"""Read-only Kubernetes lookups: rollout hashes and the image behind a hash."""

from dataclasses import dataclass

from kubernetes import client, config
from kubernetes.client.rest import ApiException


class KubeError(RuntimeError):
    pass


@dataclass(frozen=True)
class RolloutHashes:
    stable: str
    canary: str | None


def tag_of(image: str) -> str:
    """veto-shop:pr-2-ac3b97a -> pr-2-ac3b97a. Digest only images have no tag."""
    name = image.split("@", 1)[0]
    last = name.rsplit("/", 1)[-1]
    return last.split(":", 1)[1] if ":" in last else ""


class Kube:
    def __init__(self, context: str | None = None):
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config(context=context)
        self._core = client.CoreV1Api()
        self._custom = client.CustomObjectsApi()

    def rollout_hashes(self, namespace: str, name: str) -> RolloutHashes:
        try:
            ro = self._custom.get_namespaced_custom_object("argoproj.io", "v1alpha1", namespace, "rollouts", name)
        except ApiException as e:
            raise KubeError(f"rollout {namespace}/{name}: {e.reason}") from e
        status = ro.get("status") or {}
        stable = status.get("stableRS")
        current = status.get("currentPodHash")
        if not stable:
            raise KubeError("rollout has no stable replicaset yet")
        canary = current if current and current != stable else None
        return RolloutHashes(stable=stable, canary=canary)

    def image_for_hash(self, namespace: str, pod_hash: str, container: str | None = None) -> str:
        try:
            pods = self._core.list_namespaced_pod(namespace, label_selector=f"rollouts-pod-template-hash={pod_hash}")
        except ApiException as e:
            raise KubeError(f"pods for {pod_hash}: {e.reason}") from e
        for pod in pods.items:
            for c in pod.spec.containers:
                if container is None or c.name == container:
                    return c.image
        raise KubeError(f"no running pod for hash {pod_hash}")
