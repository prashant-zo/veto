# eval: meta-models/muse-spark-open-1026

| case | expected | veto | decided by | baseline | slowest run |
|---|---|---|---|---|---|
| control | hold | hold (right), hold (right), hold (right) | policy | promote (looser) | - |
| pr-1 | hold | hold (right), hold (right), hold (right) | model | promote (looser) | 7.4s |
| pr-2 | abort | abort (right), abort (right), abort (right) | model | promote (looser) | 9.9s |
| pr-3 | promote | promote (right), promote (right), promote (right) | model | promote (right) | 8.0s |
| pr-4 | abort | abort (right), abort (right), abort (right) | floor | abort (right) | - |
| pr-5 | abort | abort (right), abort (right), abort (right) | floor | promote (looser) | - |
| pr-6 | promote | promote (right), promote (right), promote (right) | model | promote (right) | 10.7s |
| pr-7 | abort | abort (right), abort (right), abort (right) | model | promote (looser) | 5.8s |

veto: 24 of 24 right, 0 stricter, 0 looser, 0 shipped that should not have

baseline: 9 of 24 right, 0 stricter, 15 looser, 15 shipped that should not have
