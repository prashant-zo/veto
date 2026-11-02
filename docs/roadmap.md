# roadmap

Two goals before Wed Nov 4, 6 PM IST: anyone can install Veto on their own cluster, and the hackathon video ships.
Hard deadline: Wed Nov 4, 9 PM ET (Thu Nov 5, 7:30 AM IST). Marks: [ ] todo, [~] doing, [x] done.

## hackathon close
- [x] blind prs judged on the frozen code: pr 6 right, pr 7 held instead of aborted, nothing shipped
- [x] blind labels from the author, scored without asking the model again (make rescore)
- [ ] post-blind fixes: a call shift of exactly 50 percent counts, a unanimous model abort stands.
      pr 7 captured again, eval and attacks run again, readme shows before and after
- [ ] video script approved
- [ ] animated scenes rendered
- [ ] live parts and voice recorded
- [ ] video edited and uploaded
- [ ] submission form, post on x

## open source anyone can deploy
1. [ ] helm chart in deploy/helm/veto: service, rbac, model secret or an existing one, the analysis template.
       done when helm install works on kind and the gated demo runs from it
2. [ ] evidence config: metric names, label names and the log selector come from values, defaults fit the otel setup.
       done when the tests pass with a second config and eval and attacks give the same results
3. [ ] quickstart: from a cluster that already has argo rollouts, prometheus and loki to a gated rollout in 10 minutes
4. [ ] chart published as an oci chart on ghcr.io and listed on artifacthub
5. [ ] second demo app in another language, so the evidence code is not only tested on python
6. [ ] model endpoint docs and self hosted muse weights, after judging ends
7. [ ] veto verdict shown as a check on the pull request, after the hackathon

## after
- github action and github app packaging, looking at how pr-agent does it
- paid setup for teams: pilot, integration, support
