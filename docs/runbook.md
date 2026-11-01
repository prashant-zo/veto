# runbook

## start
make up        colima and kind
make stack     argo rollouts, prometheus, loki, otel collector
make shop      shop and load generator

## release
cd ../veto-demo-shop && make build PR=<n>      build and load image into kind
make release SVC=checkout TAG=pr-<n>-<sha>    start a canary (50 percent, then pause)
kubectl argo rollouts -n shop get rollout checkout

## stop a canary
make abort SVC=checkout                        canary scaled down, rollout goes Degraded
make release SVC=checkout TAG=main-a13119d     back to Healthy on the stable tag
make promote SVC=checkout                      or ship the canary

## look at data
scripts/prom.sh '<promql>'
scripts/loki.sh '<logql>' [since]

## if things break
pod crashes: kubectl -n shop logs <pod> --previous
cluster broken after a colima restart: make down, make up, make stack,
then kind load docker-image veto-shop:<tag> --name veto for each tag, then make shop
