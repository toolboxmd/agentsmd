# First principles

Use this reference when the path is analogy, inherited process, an accepted
impossibility, or a novel design. Skip it on a clear microfix.

## Procedure

1. State the accepted claim in one sentence. The assumptions live in that
   phrasing.
2. List every assumption clause by clause.
3. Label each as binding or habit. Binding: physics, math, law, confirmed
   Project Direction, explicit user constraints, and measured repository or
   live-system evidence. Habit: analogy to another project, industry default,
   vendor packaging, prior ticket wording, or unowned "we always" process.
4. Drop habit unless evidence shows it is required for the outcome, proof,
   safety, or a Human Gate.
5. Rebuild the useful outcome from the binding set only. That rebuilt
   statement is the input to Algorithm step 1.

Reasoning by analogy is the default for ordinary work that already has a known
safe workflow. First principles is the override when convention is the blocker.

Repeated repairs that fail through the same premise are evidence to revisit that
premise. Name it and choose an observation distinguishing it from alternatives.
For a resource imbalance, count all actors creating and holding the state before
adding another cleanup step. For another problem, choose its relevant falsifier.
Use [software-design](../../software-design/index.md) for competing implementation shapes and [diagnosis](../../diagnosis/index.md) for
controlled causal investigation; failed repairs do not automatically justify a rewrite.

Do not use this reference to waive Human Gates, user-owned dirty work, or
confirmed Project Direction.
