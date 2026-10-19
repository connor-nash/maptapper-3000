# MapTapper 3000 — Architecture

## Overview

A single-process Discord bot built with discord.py. One SQLite database on a persistent Fly.io volume. No web server, no message queue, no external APIs beyond Discord. Game dates are always taken from the paste text — never derived from the server clock or any timezone. Mountain Time (`mt_today()` in `config.py`) is used only for scheduled summary timing and rolling average windows.

---

## Startup Sequence

1. `bot.py` loads environment variables (`.env` locally, Fly secrets in prod).
2. `MapTapper.setup_hook()` runs before the bot connects to Discord:
   - `db.init_db()` creates tables and runs any pending migrations (currently: adds `is_legacy` column if missing).
   - `_seed_legacy_scores()` inserts the three pre-bot best scores if no legacy rows exist yet. Runs on every boot but exits immediately if already seeded.
   - All six cogs are loaded: `listener`, `leaderboard`, `stats`, `achievements_cmd`, `admin`, `scheduler`.
   - Slash commands are synced globally via `tree.sync()`.
3. `Scheduler.before_check()` fires after the bot is ready (before the minute loop starts):
   - `_post_pending_summaries()` — posts any daily/weekly/monthly summaries that were missed while the bot was down.
   - `_check_shakeup_catchup()` — posts an all-time shakeup embed if the top 3 changed since the last announced state.

---

## Score Paste Flow

When a user pastes a MapTap share into the configured channel:

1. **`cogs/listener.py` — `on_message`**
   - Ignores bots, DMs, and messages outside the configured score channel (channel ID stored in `bot_config`).
   - `looks_like_maptap(content)` — quick string check for "maptap.gg". If false, silently ignores.
   - `parse_maptap_share(content)` — full regex parse (see Parser section). If parse fails, reacts ❌.

2. **`parser.py` — `parse_maptap_share`**
   - Regex matches: header line (`www.maptap.gg Month Day`), five round scores with trailing emoji, final score line.
   - Extracts month name → integer via `MONTHS` dict.
   - Game date year = `mt_today().year` — the date in the paste is always authoritative; no adjustment for timezone.
   - Returns `ParsedScore(game_date, round_scores, final_score)` or `None`.

3. **Back in `on_message`:**
   - `db.upsert_player(discord_id, display_name)` — creates or updates the player record. Returns `player_id`.
   - Snapshots the current all-time top 3 (`pre_rows`).
   - `db.insert_score(player_id, game_date, round_scores, final_score)` — inserts with `UNIQUE(player_id, game_date)` constraint. Returns `False` if a score for that player/date already exists (first post wins). On duplicate, reacts ✅ and exits.
   - Reacts ✅.
   - Compares new all-time top 3 against `pre_rows`. If top-3 best scores changed, calls `embeds.shakeup_embed()` and posts it, then updates `bot_config.last_top3`.
   - `ach.check_immediate_achievements(player_id, round_scores, final_score, game_date)` — checks perfect score, turkey, score milestones, perfect-round milestones, sixty_nine. Each type is idempotent (checks `has_achievement` before recording). Returns list of triggered achievement dicts.
   - For each triggered achievement, posts an immediate embed to the channel.

---

## Slash Command Flow

All slash commands follow the same pattern: `defer()` → DB queries → `followup.send(embed=...)`.

**`/leaderboard [view]`** (`cogs/leaderboard.py`):
- Default view: `alltime`. Options: alltime, daily, weekly, monthly, handicap.
- `daily` → `db.get_scores_for_date(mt_today())` → `embeds.daily_leaderboard_embed`
- `weekly` → `db.compute_weekly_scores(iso_year, iso_week)` → `embeds.weekly_leaderboard_embed`
- `monthly` → `db.compute_monthly_scores(year, month)` → `embeds.monthly_leaderboard_embed`
- `alltime` → `db.get_all_time_leaderboard()` → `embeds.all_time_leaderboard_embed` (ranked by `MAX(final_score)`)
- `handicap` → iterates all players with ≥5 games, fetches 30-day rolling avg per player, computes `adjusted = today_score + (group_avg − personal_avg)`, excludes players who haven't posted today.

**`/mystats` / `/stats @user`** (`cogs/stats.py`):
- Fetches all non-legacy scores for the player, computes streak, turkeys, perfect scores, fumbles, perfect round count, 69 count, rolling avg.

**`/achievements`** (`cogs/achievements_cmd.py`):
- Fetches all achievement rows for the player, groups by normalized type, renders counts.

**`/admin` commands** (`cogs/admin.py`):
- All require Administrator permission (enforced via `app_commands.checks.has_permissions`).
- `set-channel` → writes `score_channel_id` to `bot_config`.
- `reset` → deletes all rows from scores, achievements, summaries_posted, players. Does NOT wipe `bot_config`.
- `status` → reads `score_channel_id` from `bot_config`.
- `link-player` → calls `db.link_player(username, discord_id)` to merge a legacy seed account into a real player.

---

## Scheduled Summary Flow

`cogs/scheduler.py` runs a `tasks.loop(minutes=1)`. Every minute it checks if `datetime.now(TIMEZONE).hour == 7` and `minute == 0`. If so, it calls `_post_pending_summaries()`.

**`_post_pending_summaries()`** also runs on startup (catch-up):
- Checks `summaries_posted` table before posting each summary type. Posts are idempotent.
- **Daily** — always posts yesterday's summary. Posts the daily leaderboard embed plus any fumble/twinsies achievements.
- **Weekly** — on Monday only, posts the previous week's summary. Posts weekly leaderboard plus "I Think Yer Fuckin' Lost Bud" achievement.
- **Monthly** — on the 1st only, posts the previous month's summary. Posts monthly leaderboard plus most_improved, get_a_life, mia achievements.

---

## Database Schema

```sql
players (
    id              INTEGER PK AUTOINCREMENT,
    discord_id      TEXT UNIQUE,   -- real Discord snowflake, or "seed:{username}" for pre-linked legacy players
    username        TEXT,          -- Discord display_name at time of last score post
    created_at      TEXT
)

scores (
    id              INTEGER PK AUTOINCREMENT,
    player_id       INTEGER FK → players.id,
    game_date       TEXT,          -- "YYYY-MM-DD", from paste text
    round_scores    TEXT,          -- JSON array e.g. "[88,96,97,97,7]"
    final_score     INTEGER,
    is_legacy       INTEGER,       -- 1 = pre-bot seed score; excluded from daily/weekly/monthly queries
    posted_at       TEXT,
    UNIQUE(player_id, game_date)
)

achievements (
    id              INTEGER PK AUTOINCREMENT,
    player_id       INTEGER FK → players.id,
    achievement_type TEXT,
    period          TEXT,          -- game date, "YYYY-W{ww}", or "YYYY-MM"
    metadata        TEXT,          -- JSON or NULL
    created_at      TEXT
)

summaries_posted (
    summary_type    TEXT,          -- "daily" | "weekly" | "monthly"
    period          TEXT,          -- "YYYY-MM-DD" | "YYYY-W{ww}" | "YYYY-MM"
    posted_at       TEXT,
    PRIMARY KEY (summary_type, period)
)

bot_config (
    key     TEXT PK,
    value   TEXT
)
```

---

## Weekly Scoring Logic

For a given ISO week (Mon–Sun):
1. Collect all non-legacy scores for the week, grouped by player.
2. Each player has 7 slots. Unplayed days = 0.
3. Sort all 7 values ascending, drop the 2 lowest, sum the remaining 5 → `weekly_score`.
4. `weekly_avg = weekly_score / 5`.
5. Players who played zero days that week appear in the output with `weekly_score = 0`.

---

## Monthly Scoring Logic

For a given calendar month:
1. Collect all non-legacy scores for the month, grouped by player.
2. Each player has `days_in_month` slots. Unplayed days = 0.
3. Sort all slots ascending, drop the 8 lowest (`MONTH_DROPS`), sum the rest → `monthly_score`.
4. `monthly_avg = monthly_score / (days_in_month - 8)`.
5. Missed days absorb drops first: a player who missed 10 days of a 30-day month will have 8 zeros dropped, leaving 2 zeros + all real scores in the kept set. Only if fewer than 8 days were missed do any real scores get dropped.

---

## Legacy Score / Account Linking

Three players had best scores before the bot existed. These were seeded on first boot via `_seed_legacy_scores()` using placeholder `discord_id` values (`seed:{username}`). `db.link_player(username, real_discord_id)` merges the seed record into the real player: if the real Discord user already has a player row (because they've since posted a live score), their scores and achievements tables are re-pointed to the real player ID and the seed row is deleted. If not, the seed row's `discord_id` is updated to the real one.

Legacy scores have `is_legacy = 1`. They appear in all-time leaderboard but are excluded from daily, weekly, monthly, rolling average, streak, and achievement queries.

---

## External Dependencies

| Dependency | Purpose |
|---|---|
| Discord API (gateway) | Receives messages and slash command interactions |
| discord.py 2.x | Async Discord client library |
| aiosqlite | Async SQLite driver |
| pytz | IANA timezone database for Mountain Time |
| python-dotenv | Loads `.env` for local development |
| Fly.io | Hosting platform; provides the persistent volume and secret storage |
| GitHub Actions | Triggers `flyctl deploy` on push to `main` |
