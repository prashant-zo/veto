# 0002 the ai can explain a change, never approve it

status: accepted

Hard failures like an error rate breach abort before the model runs.
Code computes a ceiling from the evidence before the model is called.
Any hard anomaly (call edge added or gone, error or latency shift, new error log) caps the verdict at HOLD.
Final verdict is the model verdict capped at the ceiling.
Anything unclear (timeout, bad json, no PR found, low traffic) falls back to HOLD.

Why: a prompt injection or a wrong answer can at worst pause a release. It can never ship one.
