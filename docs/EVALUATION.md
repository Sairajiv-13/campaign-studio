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

## Real-model validation (attempted, hardware-blocked)

The numbers above use the deterministic sandbox judge, so they describe the
scorer's *rubric*, not a real model's brand-voice judgment. I tried to close that
gap by running the same eval with `LLM_MODE=real` against local Ollama.

It didn't run on my hardware. The dev machine has 6 GB of RAM; `llama3.2:3b` needs
~2.9 GB and `llama3.2:1b` ~1.4 GB, and with a browser open there was under 1 GB
free. Both models loaded but then swapped to disk on every token — a single "say
OK" call took over four minutes and usually timed out. My own retry logic caught
it correctly (three transient retries, then a clean `TransientLlmError`), which at
least confirms that path works, but there were no useful judgments to score.

Two honest takeaways rather than one:

1. The adapter is validated against a mocked OpenAI server (`tests/unit/`), so the
   request/response and retry behavior are covered. What's *not* covered is a real
   model's judgment quality on this task.
2. A ~1B judge would very likely be noisier than the deterministic heuristics
   anyway, so "real" here doesn't automatically mean "better." The right comparison
   is an 8B-class model.

To reproduce on adequate hardware (or a hosted OpenAI-compatible endpoint):

```bash
# local, needs ~8 GB free
ollama pull llama3.1
LLM_MODE=real LLM_MODEL=llama3.1 LLM_BASE_URL=http://localhost:11434/v1 \
  python -m evals --json real.json

# or any hosted endpoint (Groq, OpenAI, vLLM, ...)
LLM_MODE=real LLM_BASE_URL=... LLM_API_KEY=... LLM_MODEL=... python -m evals
```

The five heuristic dimensions should be **identical** to the sandbox run — they
never call a model — so any movement in the table isolates exactly what the LLM
judge contributes to `brand_voice`. That diff is the experiment worth running.

## What I'd measure next

1. Re-run the whole set against a real model and diff the per-lever table — the
   heuristic dimensions should be unchanged, so any movement isolates the judge.
2. Add a specificity dimension and see whether `a03` flips without regressing the
   single-lever pairs.
3. Grow the set toward ~50 pairs with a second labeler, and report agreement.
