# 0012 prompt injection defense

status: accepted

PR text, commits, diffs and logs are written by whoever made the change, so every one is untrusted.
Layers, outside in:
1. clean: unicode folded (NFKC), invisible and control characters and terminal escapes dropped
2. redact: keys, tokens, passwords, emails, ips and long encoded blobs replaced before anything leaves
3. detect: text aimed at the reviewer is hard evidence, one strong sign or 3 signs abort before the model.
   log lines that look like attacks are kept as they are, masking key=value would hide the words
4. mark: the bundle sits between tags made from its hash, text inside cannot fake the end
5. cap: hard evidence means hold at most, whatever the model says
6. check: 3 runs must agree, promote must explain every id, soft log changes must be in the diff

The attack suite (make attacks) plants 16 payloads in 80 places of real bundles. Results in eval/results.
Known gaps: other languages, homoglyphs and plain social engineering pass the detector. The model and the
cap handle those, and the suite counts how often the model alone was fooled.
