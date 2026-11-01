# 0008 log templates by masking

status: accepted

Each log line is cleaned and redacted first, then values are masked (key=value, numbers, ids, url query)
to get a template. Canary and stable templates are compared exactly, counted per request.
The first 90s of each side's logs count too, so a line logged once at startup is not missed.
Canary text that talks to the reviewer (verdict, approve, ignore instructions) is hard evidence.

Why not Drain3: it merges lines that differ by one word, and a changed word is what we look for.
Cost: free text values without key=value stay in the template and can show up as new templates.
