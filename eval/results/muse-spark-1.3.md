# eval: muse-spark-1.3

| case | expected | veto | decided by | baseline | slowest run |
|---|---|---|---|---|---|
| control | hold | hold (right) | model | promote (looser) | 21.7s |
| pr-1 | hold | hold (right) | model | promote (looser) | 8.9s |
| pr-2 | abort | abort (right) | model | promote (looser) | 8.4s |
| pr-3 | promote | promote (right) | model | promote (right) | 6.3s |
| pr-4 | abort | abort (right) | floor | abort (right) | - |
| pr-5 | abort | abort (right) | floor | promote (looser) | - |

veto: 6 of 6 right, 0 stricter, 0 looser, 0 shipped that should not have

baseline: 2 of 6 right, 0 stricter, 4 looser, 4 shipped that should not have
