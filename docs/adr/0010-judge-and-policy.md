# 0010 judge and policy

status: accepted

Order of a decision, built on adr 0002:
1. the bundle hash must match its content, else no decision
2. floor: 10 points more errors on canary, or text aimed at the reviewer (one strong sign or 3 signs),
   aborts before the model runs
3. ceiling: any hard evidence, low traffic, partial logs or no PR caps the verdict at hold
4. the model runs 3 times at temperature 0, all runs must parse and agree, else hold
5. promote needs every evidence id marked explained in every run, and every soft log item must show up
   in an added or removed line of a source file in the diff
6. final verdict is the stricter of the model verdict and the ceiling

The prompt marks the bundle with a tag made from its hash, so text inside cannot fake the end of it.
Muse Spark Open on Baseten answers first, Muse Spark 1.3 on the Meta API takes over when it fails.

Why: the model reads intent against evidence, the only thing code cannot do. Everything around it is code,
so a fooled or broken model can at worst hold a release.
