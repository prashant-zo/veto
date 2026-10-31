# state

## now
part 1: read license, ask friends for blind test prs

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
- meta api card fixed, smoke test: 5 of 5 abort, same ids, mean 3.7s

## facts
- mac air m1, 8 GB ram, macOS 15.8.1, arm64
- repo path: /Users/prashant/Documents/The Helios Project/DevOps/Project/veto (has spaces, always quote)
- all projects live in .../DevOps/Project/
- python 3.12.13 via uv, system python is 3.14 and unused
- colima 0.10.1, default profile 2 cpu 4 GiB, resize before cluster
- kind 0.31.0, kubectl 1.36.0, helm 3.20.2, gitleaks 8.30.1, gh 2.103.3, pre-commit 4.6.0
- kubectl-argo-rollouts comes from argoproj/tap, tap not trusted yet
- git user prashant-zo, noreply email, push over ssh
- env vars: VETO_MODEL_BASE_URL, VETO_MODEL_NAME, VETO_MODEL_API_KEY
- openai python client 3.42.0, chat.completions works on both providers
- main judge: meta-models/muse-spark-open-1026 at https://inference.baseten.co/v1, config in .env
- baseten: reasoning comes in message.reasoning_content, content is clean json
- fallback judge: muse-spark-1.3 at https://api.meta.ai/v1, config in .env.meta
- meta api: chat completions works, reasoning not returned, only counted in usage
- both accept response_format json_object
- latency 3 to 4.5s per call on a small bundle, both providers
- cluster name: veto, context kind-veto
- demo shop repo: prashant-zo/veto-demo-shop, not created yet
- image tag format: pr-<number>-<shortsha>

## rules
- commit and push after every step, short lowercase message
- no secrets in git, keys only in .env files or k8s secrets
- read a file before changing it
- only muse in demo, eval and site until judging ends

## open
- glimmer access not confirmed
- modal and fireworks credits pending
