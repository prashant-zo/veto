# eval: meta-models/muse-spark-open-1026

| case | expected | veto | decided by | baseline | slowest run |
|---|---|---|---|---|---|
| control | hold | hold (right), hold (right), hold (right) | policy | promote (looser) | - |
| pr-1 | hold | hold (right), hold (right), hold (right) | model | promote (looser) | 7.1s |
| pr-2 | abort | abort (right), abort (right), abort (right) | model | promote (looser) | 9.9s |
| pr-3 | promote | promote (right), promote (right), promote (right) | model | promote (right) | 7.9s |
| pr-4 | abort | abort (right), abort (right), abort (right) | floor | abort (right) | - |
| pr-5 | abort | abort (right), abort (right), abort (right) | floor | promote (looser) | - |
| pr-6 | held out | promote (held out), promote (held out), promote (held out) | model | promote (held out) | 9.7s |
| pr-7 | held out | hold (held out), hold (held out), hold (held out) | model | promote (held out) | 11.3s |

veto: 18 of 18 right, 0 stricter, 0 looser, 0 shipped that should not have

baseline: 6 of 18 right, 0 stricter, 12 looser, 12 shipped that should not have
