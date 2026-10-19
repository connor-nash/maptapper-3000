# MapTapper 3000 — Project Guide

## How We Work

**Before starting any coding task:** Read `ARCHITECTURE.md` to understand how the system currently works. Do not rely on CLAUDE.md alone — ARCHITECTURE.md is the authoritative description of runtime behavior, data flows, and component interactions.

**After making changes:** Always summarize what changed in plain English and explain the real-world impact — what the user will see or experience differently, what behavior changed, what risk was removed. Do not just describe the code.

**When planning:** Explain the plan in real-world terms — what will happen, what will look different, what could go wrong. For any UI feature, include an ASCII mockup before writing any code so the layout is agreed on first.

**When you are wrong or miss something:** Present the fix. No excuses, no spin, no framing a failure as partial success.

**Before diagnosing a problem:** Trace it before asserting. Do not suggest cache clearing, redeployment, or environmental causes until you have ruled out a logic error in the code.

**TODO.md scope:** Code changes only — bugs, features, and ideas that require writing code. No deployment steps, no verification checklists, no testing instructions.

---

## Coding Style

- No comments unless the WHY is genuinely non-obvious. Good names eliminate the need for comments.
- No debug output (print statements, log calls, breakpoint artifacts) in production code — remove before committing.
- Don't add features, refactor, or introduce abstractions beyond what the task requires. Three similar lines is better than a premature abstraction.
- Don't add error handling for scenarios that can't happen. Only validate at real system boundaries — user input, external APIs, file I/O.
- Don't design for hypothetical future requirements. Write what the task needs now.
- Prefer editing existing files over creating new ones.

**Project-specific:**
- Never use `date.today()` or `datetime.now()` anywhere — always use `mt_today()` from `config.py`. The Fly.io server runs UTC; `mt_today()` returns the current date in America/Denver.
- `round_scores` is always a JSON string in SQLite. Parse with `json.loads()` on every read; serialize with `json.dumps()` on every write. Never store or pass it as a Python list directly across the DB boundary.
- Slash command handlers must call `interaction.response.defer()` before any async DB work, then `interaction.followup.send()`.
- Achievement period keys: immediate = `YYYY-MM-DD` (game date); weekly = `{year}-W{week:02d}`; monthly = `{year:04d}-{month:02d}`.

---

## Project Overview

MapTapper 3000 is a Discord bot that tracks daily scores for the geography game maptap.gg. Players paste their share text into a configured channel; the bot parses the paste, stores the score, checks for achievements, and posts scheduled leaderboard summaries. It serves a single Discord server with a small group of competitive daily players.

---

## File Map

| File | Role |
|---|---|
| `bot.py` | Entry point. Defines `MapTapper` bot subclass, loads cogs, seeds legacy scores on first boot. |
| `config.py` | All constants and the `mt_today()` helper. Single source of truth for timezone, thresholds, milestones. |
| `database.py` | All SQLite reads/writes via aiosqlite. Schema init, migrations, every query. |
| `parser.py` | Parses raw MapTap share text into a `ParsedScore` dataclass. |
| `achievements.py` | All achievement detection logic (immediate, daily, weekly, monthly). |
| `embeds.py` | All Discord embed builders. No business logic — formatting only. |
| `cogs/listener.py` | `on_message` handler. Parses scores, writes to DB, fires immediate achievements and shakeup embeds. |
| `cogs/leaderboard.py` | `/leaderboard` slash command with daily/weekly/monthly/alltime/handicap views. |
| `cogs/stats.py` | `/mystats` and `/stats @user` slash commands. |
| `cogs/achievements_cmd.py` | `/achievements` slash command. |
| `cogs/admin.py` | `/admin` command group: set-channel, reset, status, link-player. |
| `cogs/scheduler.py` | Minute-tick loop that posts daily/weekly/monthly summaries at 7 AM MT. Catch-up on startup. |
| `seed.py` | One-time script used during initial setup to seed legacy best scores. Not run in production. |
| `Dockerfile` | Python 3.12-slim image. Mounts `/app/data` as the persistent volume for the SQLite DB. |
| `fly.toml` | Fly.io app config: region, volume mount, `DB_PATH` env var. |
| `.github/workflows/deploy.yml` | GitHub Actions: auto-deploys to Fly.io on every push to `main`. |
| `env.example` | Template for local `.env` file. Only `DISCORD_TOKEN` is required. |
| `SETUP.md` | Human-readable first-time setup guide. |

---

## Deployment

- **Platform:** Fly.io (free tier, `dfw` region), single shared-CPU machine with 1 GB RAM.
- **Database:** SQLite at `/app/data/maptap.db` on a persistent Fly volume named `data`. Never in-memory, never the container filesystem.
- **CI/CD:** GitHub Actions deploys on every push to `main` via `flyctl deploy --remote-only`. The `FLY_API_TOKEN` secret must be set in the GitHub repo.
- **Secrets:** Only `DISCORD_TOKEN` — set via `fly secrets set DISCORD_TOKEN=...`, never committed.
- **Local dev:** Copy `env.example` → `.env`, run `python bot.py`. SQLite DB writes to `maptap.db` in the project root (covered by `.gitignore`).

---

## Configuration

```python
# config.py

TIMEZONE = pytz.timezone("America/Denver")  # All date operations use this — never UTC, never local system time

def mt_today():                              # Returns today's date in Mountain Time — use this everywhere instead of date.today()
    return datetime.now(TIMEZONE).date()

SUMMARY_HOUR = 7                             # Hour (MT) when daily/weekly/monthly summaries post
SUMMARY_MINUTE = 0                           # Minute for summaries

EMBED_COLOR = 0x2ECC71                       # Discord embed accent color (green)
MAPTAP_URL = "https://www.maptap.gg"        # Linked in every embed

ROUND_WEIGHTS = [1, 1, 2, 3, 3]             # Per-round score multipliers; weighted sum = final_score
ROUND_MAX_WEIGHTED = 1000                    # Max possible final_score

FUMBLE_PROJECTED_THRESHOLD = 960            # Projected score (worst-round-replaced) must be >= this for a Fumble
CLIFF_DROP_THRESHOLD = 200                  # Point drop from previous score that triggers the Cliff achievement
SCORE_MILESTONES = [100_000, 250_000, 500_000, 1_000_000]  # Cumulative score milestone thresholds
PERFECT_ROUND_MILESTONES = [100, 200, 300, 500]             # Cumulative perfect-round milestone thresholds

WEEK_DAYS = 7                                # Slots per weekly leaderboard (Mon–Sun)
WEEK_DROPS = 2                               # Lowest scores dropped each week before summing
MONTH_DROPS = 8                              # Lowest scores dropped each month (fixed regardless of month length)

HANDICAP_WINDOW_DAYS = 30                    # Rolling average window for handicap calculation
MIN_HANDICAP_GAMES = 5                       # Minimum games played before player appears in handicap leaderboard
```

**Environment variables:**
```
DISCORD_TOKEN   # Discord bot token — required, loaded from .env locally, Fly secret in production
DB_PATH         # SQLite file path — defaults to "maptap.db"; overridden to "/app/data/maptap.db" via fly.toml
```

---

## Platform Rules

- **`fly ssh console` is broken** (returns 502). Use `fly machine exec <machine-id> "python3 -c \"...\""` to run one-off DB queries or fixes against the live database.
- **Fly.io machine ID** is needed for `fly machine exec`. Get it with `fly machine list`.
- **Slash command sync** happens in `setup_hook` via `await self.tree.sync()`. Changes to slash command signatures require a redeploy; they won't update in Discord until the bot restarts.
- **Message Content Intent** must be enabled in the Discord Developer Portal (Bot tab → Privileged Gateway Intents). Without it, `on_message` receives messages with empty `content`.
- **WAL mode** is enabled on the SQLite DB. Do not open the DB file with tools that don't support WAL — they may see stale data or corrupt the journal.
- **Persistent volume** survives redeploys and restarts but is tied to a single Fly region. Do not change `primary_region` without also migrating the volume.

---

## Data Shapes

**`ParsedScore` (from `parser.py`):**
```python
@dataclass
class ParsedScore:
    game_date: str          # "YYYY-MM-DD" — always authoritative from the paste text
    round_scores: list[int] # [r1, r2, r3, r4, r5], each 0–100
    final_score: int        # weighted sum; max 1000
```

**Score row (from `get_scores_for_date` etc.):**
```python
{
    "id": int,
    "player_id": int,
    "game_date": str,         # "YYYY-MM-DD"
    "round_scores": str,      # JSON — always call json.loads() before use
    "final_score": int,
    "is_legacy": int,         # 1 = seeded best-score only, excluded from daily/weekly/monthly
    "posted_at": str,
    "discord_id": str,        # joined from players table
    "username": str,          # joined from players table; may differ from Discord display name after rename
}
```

**Achievement row:**
```python
{
    "player_id": int,
    "achievement_type": str,  # "perfect_score" | "turkey" | "fumble" | "twinsies" | "lost_bud" |
                              # "most_improved" | "get_a_life" | "mia" | "sixty_nine" |
                              # "cliff" | "deja_vu" |
                              # "score_milestone_{N}" | "perfect_round_milestone_{N}"
    "period": str,            # game date "YYYY-MM-DD" (immediate) | "YYYY-W{ww}" (weekly) | "YYYY-MM" (monthly)
    "metadata": str,          # JSON or NULL — structure varies by type
}
```

**Weekly leaderboard entry (from `compute_weekly_scores`):**
```python
{
    "discord_id": str,
    "username": str,
    "weekly_score": int,    # sum of 5 kept scores (after dropping 2 lowest of 7 slots)
    "weekly_avg": float,    # weekly_score / 5
    "best_score": int,
    "games_played": int,    # actual days played (not slots filled)
}
```

**Monthly leaderboard entry (from `compute_monthly_scores`):**
```python
{
    "discord_id": str,
    "username": str,
    "monthly_score": int,   # sum of kept scores after dropping 8 lowest slots (missed days = 0)
    "monthly_avg": float,   # monthly_score / (days_in_month - 8)
    "best_score": int,
    "games_played": int,    # actual days played (not slots)
}
```

**All-time leaderboard row (from `get_all_time_leaderboard`):**
```python
{
    "discord_id": str,
    "username": str,
    "total": int,           # cumulative final_score (includes legacy)
    "games_played": int,
    "avg_score": float,
    "best_score": int,      # MAX(final_score) — this is the sort key
}
```

**`bot_config` table keys:**
```
"score_channel_id"   # Discord channel ID (string) where scores are watched and summaries post
"last_top3"          # JSON: [{"username": str, "best_score": int}, ...] — last announced all-time top 3
```

---

## Project Docs

| File | Role |
|---|---|
| `CLAUDE.md` | Collaboration rules, coding style, config, data shapes — update when any of these change |
| `ARCHITECTURE.md` | Factual description of how the system works right now — update when behavior changes |
| `TODO.md` | Bugs, planned features, and ideas — check items off as they are completed |
