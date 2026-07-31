# Task 3 report — Overlay HTML pages (no brand assets)

## Status
**Done**

## Commits
- `d912f7c` — `feat(marcato): add personal overlay HTML pages`

## Deliverables
| File | Notes |
|------|--------|
| `overlays-marcato/starting-soon.html` | Lockup, session badge, countdown via `../overlays/*.js` |
| `overlays-marcato/brb.html` | PiGreco-matching `data-brb-*` hooks + `brb-timer.js` |
| `overlays-marcato/ending.html` | Twitch CTA only (no QR img) |
| `overlays-marcato/live-chrome.html` | Session badge, cam frame, lower-third; no sponsors/telemetry |
| `overlays-marcato/ending-cta.js` | Twitch-only CTA; hides QR if present |
| `tests/test_marcato_profile.py` | `test_marcato_html_has_no_pigreco_assets` |

## Tests
```
python -m pytest tests/test_marcato_profile.py -v
→ 4 passed (including brand-leak test)
```

## Manual smoke
Open `file:///.../overlays-marcato/starting-soon.html` (and siblings) in a browser; lockup + countdown/BRB areas should render with `theme.css`.

## Concerns
- `ending-cta` block has no dedicated rules in `overlays-marcato/assets/theme.css` yet (inherits panel typography); optional polish in a later task.
- `live-chrome` uses text lockup in lower-third only (no watermark bar) to avoid logo patterns.

## Branch
`feat/s-marcato-42`

---

## Task 3 follow-up (title + ending CTA)

**Status:** Done

### Changes
- `overlays-marcato/config.runtime.js`: `document.title` fallback `PiGreco` → `S.Marcato`; regenerated `config.js`.
- `overlays-marcato/assets/theme.css`: minimal `.ending-cta` / `.ending-cta-text` / `.ending-follow` (steel, centered, no card chrome).
- `tests/test_marcato_profile.py`: brand-leak scan includes `ending-cta.js`.

### Tests
```
python -m pytest tests/test_marcato_profile.py -v
→ 4 passed
```

### Commit
`fix(marcato): personalize title fallback and ending CTA styles`
