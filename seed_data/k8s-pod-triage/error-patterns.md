| Status | Usually means |
|---|---|
| ImagePullBackOff | Wrong tag, private registry, or missing imagePullSecret |
| CrashLoopBackOff | The process exits immediately — read the previous log |
| Pending, no events | No node satisfies the resource requests or node selector |
| OOMKilled | Memory limit is below actual usage, not a leak by itself |
| CreateContainerConfigError | A referenced ConfigMap or Secret does not exist |
