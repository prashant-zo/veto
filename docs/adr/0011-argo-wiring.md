# 0011 argo rollouts wiring

status: accepted

Veto runs as a small service in the cluster. A ClusterAnalysisTemplate calls GET /v1/verdict
in an analysis step, after the canary has had 150s of traffic.
promote is success, abort is failure, hold or pending is inconclusive,
so argo continues the rollout, aborts it, or pauses it for a person.

One decision per canary hash, kept 30 minutes, so argo polls never pay for the model twice.
Each decision is also an Event on the Rollout, and the message says it comes from Veto.
Any error inside Veto answers hold. If Veto cannot be reached at all, argo's own error handling decides,
to be tested in part 6.

Why: argo already knows how to pause and abort. Veto only has to answer one question over http.
