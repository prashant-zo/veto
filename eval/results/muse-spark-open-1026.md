# eval: meta-models/muse-spark-open-1026

| case | expected | veto | decided by | baseline | slowest run |
|---|---|---|---|---|---|
| control | hold | abort (stricter), hold (right), hold (right) | model | promote (looser) | 27.6s |
| pr-1 | hold | hold (right), hold (right), hold (right) | model | promote (looser) | 17.9s |
| pr-2 | abort | abort (right), abort (right), abort (right) | model | promote (looser) | 7.6s |
| pr-3 | promote | promote (right), promote (right), promote (right) | model | promote (right) | 9.0s |
| pr-4 | abort | abort (right), abort (right), abort (right) | floor | abort (right) | - |
| pr-5 | abort | abort (right), abort (right), abort (right) | floor | promote (looser) | - |

veto: 17 of 18 right, 1 stricter, 0 looser, 0 shipped that should not have

baseline: 6 of 18 right, 0 stricter, 12 looser, 12 shipped that should not have
