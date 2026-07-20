# Evaluating the scorer

The scorer decides which variant ships. If it disagrees with a marketer, the whole
thing is decoration. So it gets measured.

## Method

18 hand-labeled A/B pairs. Each pair is two variants for the same context plus the
one a marketer would actually send. The metric is **pairwise ranking accuracy**:
does the scorer give the preferred variant the higher composite?

The winning side alternates between A and B, so a scorer with positional bias
scores ~50% rather than accidentally looking good. `mean margin` is the average
absolute gap between the two composites — it catches the case where the scorer
"wins" by a rounding error.

```bash
make eval        # python -m evals --min-accuracy 0.8
```

## Current results

```
pairs:            18
ranking accuracy: 88.9%   (16/18)
mean margin:      0.162

accuracy by lever:
  brand_voice          100%
  clarity              100%
  clickbait              0%   <- known failure
  cta                  100%
  deliverability       100%
  emphasis_caps        100%
  near_miss_banned     100%
  over_personalization   0%   <- known failure
  personalization      100%
  subject              100%
  substance            100%
  tone_subtlety        100%
```

## Why it isn't 100%, and why that's the point

The first 12 pairs each isolate one lever the scorer explicitly measures — strong
CTA vs weak, personalized vs generic, clean vs spammy. A working scorer sweeps
them. That makes them a **regression test**, not a benchmark. An eval you always
pass tells you nothing about quality; it only tells you nothing broke.

So there are 6 adversarial pairs where the copy a marketer would pick *loses* on a
measured dimension. Two of them the scorer gets wrong. Those stay in the set, and
there's a test (`test_known_failure_modes_are_still_failing`) pinning them — if
one starts passing, that's a real improvement worth noticing rather than a silent
change.

## Known failure modes

### 1. `a01` — personalization has no notion of appropriateness

Variant A cites the exact times someone browsed ("at 11pm last night, and again
this morning from your phone"). It scores maximum personalization: merge tag,
segment trait, second person. It is also the kind of email that makes people
unsubscribe.

The heuristic counts personalization signals. It cannot distinguish *relevant*
from *surveillant*, because that distinction isn't in the text — it's in social
norms. Fixing it properly means either a judge prompt that grades creepiness, or
a rule capping how specific a behavioral reference may be.

### 2. `a03` — nothing penalizes a vague hook

"You won't believe what happened" is well-formed: good subject length, no spam
words, readable, has a CTA. It's also content-free clickbait, and it loses to
"Your account has 3 new features" with any real audience.

The rubric measures the *shape* of copy, not whether it says anything. Specificity
would need its own dimension — probably a judge call, since "does this sentence
contain a concrete claim" isn't a regex.

## A caveat on the passes

`a04` (near-miss banned phrase) passes, but not for the right reason. The banned
list contains "miracle cure" and the copy says "miracle formula" — the substring
check does **not** catch that. The pair resolves correctly on other dimensions.
Treat that lever as unverified: paraphrased policy violations will get through,
which is the sort of thing that matters if this ever touched regulated copy.

## Limits worth stating plainly

- **18 pairs is small.** It catches regressions and exposes the two failure modes
  above. It is not enough to claim the scorer is objectively correct.
- **Labels are mine.** One person's marketing judgment, not a panel. Inter-rater
  agreement is unmeasured.
- **The sandbox judge is deterministic.** These numbers describe the scorer's
  *rubric*, not a real model's brand-voice judgment. Re-running with `LLM_MODE=real`
  would move `brand_voice` and is the obvious next measurement.

## What I'd measure next

1. Re-run the whole set against a real model and diff the per-lever table — the
   heuristic dimensions should be unchanged, so any movement isolates the judge.
2. Add a specificity dimension and see whether `a03` flips without regressing the
   single-lever pairs.
3. Grow the set toward ~50 pairs with a second labeler, and report agreement.
