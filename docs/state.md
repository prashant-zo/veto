# state

## now
part 1: meta card retry, read license, ask friends for blind test prs

## plan
1. repo, setup, smoke test
2. cluster and demo shop
3. evidence bundle
4. judge and policy
5. service and argo wiring
6. eval and security tests
7. helm chart and site
8. video and submit

## done
- repo with apache license, push protection on
- project layout, python 3.12 with uv
- gitleaks pre-commit hook, tested with a fake token
- state file, adrs, makefile
- smoke test against baseten: 5 of 5 abort, same ids, mean 3.3s

## facts
- mac air m1, 8 GB ram, macOS 15.8.1, arm64
- repo path: /Users/prashant/Documents/The Helios Project/DevOps/Project/veto (has spaces, always quote)
- all projects live in .../DevOps/Project/
- python 3.12.13 via uv, system python is 3.14 and unused
- colima 0.10.1, default profile 2 cpu 4 GiB, resize before cluster
- kind 0.31.0, kubectl 1.36.0, helm 3.20.2, gitleaks 8.30.1, gh 2.103.3, pre-commit 4.6.0
- kubectl-argo-rollouts comes from argoproj/tap, tap not trusted yet
- git user prashant-zo, noreply email, push over ssh
- model: meta-models/muse-spark-open-1026 at https://inference.baseten.co/v1, key works only for this model
- env vars: VETO_MODEL_BASE_URL, VETO_MODEL_NAME, VETO_MODEL_API_KEY (in .env, gitignored)
- openai python client 3.42.0, chat.completions works
- model reasoning comes in message.reasoning_content, message.content is clean json
- response_format json_object is accepted
- latency 2 to 4.5s per call on a small bundle
- cluster name: veto, context kind-veto
- demo shop repo: prashant-zo/veto-demo-shop, not created yet
- image tag format: pr-<number>-<shortsha>

## rules
- commit and push after every step, short lowercase message
- no secrets in git, keys only in .env or k8s secrets
- read a file before changing it
- only muse in demo, eval and site until judging ends

## open
- meta api account restricted (card)
- glimmer access not confirmed
- modal and fireworks credits pending
