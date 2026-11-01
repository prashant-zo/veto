# 0009 evidence bundle

status: accepted

One JSON file per canary is all the judge ever sees: both sides' stats, the PR, and evidence items.
Evidence ids say where a fact came from: M metrics and call edges, L logs, P the pull request.
The hash covers everything but the time, so each verdict points at the exact bundle it was given.

PR text and logs are untrusted. They are cleaned, redacted and cut to size before they go in,
and scanned in full for text aimed at the reviewer, which becomes hard evidence.
No PR, a tag sha that is not the PR head, or GitHub being down are hard evidence too, so the gate fails closed.

Cost: a bundle is a snapshot. A canary judged later gets a new bundle and a new hash.
