# 0010 judge and policy

status: accepted

Order of a decision, built on adr 0002:
1. the bundle hash must match its content, else no decision
2. floor: 10 points more errors on canary, or text aimed at the reviewer (one strong sign or 3 signs),
   aborts before the model runs
3. no PR, a tag sha that is not the PR head, or GitHub down holds before the model runs:
   without the intent there is nothing to check, and the model split abort and hold on it
4. ceiling: any hard evidence, low traffic or partial logs caps the verdict at hold
5. the model runs 3 times at temperature 0, all runs must parse and agree, else hold
6. promote needs every evidence id marked explained in every run, and every soft log item must show up
   in an added or removed line of a source file in the diff
7. final verdict is the stricter of the model verdict and the ceiling

The prompt marks the bundle with a tag made from its hash, so text inside cannot fake the end of it.
Muse Spark Open on Baseten answers first, Muse Spark 1.3 on the Meta API takes over when it fails.

Why: the model reads intent against evidence, the only thing code cannot do. Everything around it is code,
so a fooled or broken model can at worst hold a release.

After the blind test (Nov 2), two changes, made after the author's answer was known:
- a call shift is 30 percent or more per request, it was more than 50. pr 7 halved its payment calls and
  sat exactly on the old line, so the code saw no hard evidence
- a unanimous model abort stands even when it names no listed evidence item. Muse read the payment behind
  `if total >= 5.0` in the diff in all 9 runs, and the old rule turned that into a hold
The frozen-code result stays in the readme next to the new one.
