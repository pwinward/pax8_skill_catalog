---
name: k8s-pod-triage
description: Diagnoses a failing Kubernetes pod by working outward from its status.
---

When a pod is failing, work outward rather than guessing:

1. `kubectl get pod <name> -o wide` — note the phase and the node.
2. `kubectl describe pod <name>` — read Events from the bottom up. Most causes
   are stated there plainly: image pull failures, failed scheduling, OOMKills.
3. `kubectl logs <name> --previous` when the container has restarted. The current
   log is usually empty in a crash loop; the previous one holds the reason.
4. Only then look at the node, the service account, and the network policy.

Read `error-patterns.md` for what the common status strings actually mean.

Report the cause and the evidence for it. If the evidence is thin, say so rather
than presenting a guess as a finding.
