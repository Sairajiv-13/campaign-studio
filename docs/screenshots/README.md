# Screenshots

Drop UI captures here and reference them from the root `README.md`.

Suggested set (run `docker compose up --build`, then http://localhost:8000, and
sign in with `marketer` / `local-dev-password`):

| Filename | What to capture |
|----------|-----------------|
| `01-brief.png` | The brief form on the left. Product, tone, goal, banned phrases, and the selected segments. |
| `02-campaign-plan.png` | A generated plan: the winning variant per segment with the composite score and the five dimension bars. |
| `03-score-breakdown.png` | A close-up of one winner's score breakdown, including the warning notes (weak CTA / low personalization / deliverability risk). |
| `04-variants.png` | The expanded "Other variants" list showing the ranking that produced the winner. |
| `05-eval-report.png` | Terminal output of `make eval`. Pairwise ranking accuracy and the per-lever breakdown. |

Guidelines:

- Use a ~1280px-wide window so text stays legible when scaled down in the README.
- Prefer PNG.
- Keep any real brand names or personal data out of the captures.

Reference them from the README like:

```markdown
![Campaign plan](docs/screenshots/02-campaign-plan.png)
```
