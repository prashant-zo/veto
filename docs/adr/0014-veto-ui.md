# 0014 the veto ui

status: accepted

Veto serves one page at `/` with the decisions it made since it started, read from `/data.json`.
It is the replay page from GitHub Pages, moved to src/veto/serve/static, so one page does both:
Pages puts it next to site/data.json (the saved releases), Veto feeds it live from its own memory.

- decisions are kept in memory, the last 50. No database, no volume. A restart clears them, the Events and log lines stay.
- the full bundle and decision are kept next to each verdict for the page. `/v1/verdict`, `/v1/decisions` and the Events never carry them.
- no login. The page is reached with kubectl port-forward. It is on by default, `ui.enabled=false` turns it off.
- all bundle text goes into the page with textContent. The page is served with a content security policy that runs
  only its own inline script (by hash), allows no frames, and reads data only from Veto itself.

Why: a team running Veto wants to see what it decided on their own releases, not only the demo ones.
Cost: history is lost on restart, and anyone who can reach the service inside the cluster can read the page.
A store and auth come when someone needs them.
