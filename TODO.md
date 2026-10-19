# MapTapper 3000 — TODO

## Bugs

- [ ] **MIA and Get a Life fire for the same player** — if a player played every day, `min_games == days_in_month`, so they appear in both `get_a_life` and `mia` lists simultaneously. `check_monthly_achievements` should exclude `get_a_life` players from the MIA check.

- [ ] **Legacy scores count toward cumulative score milestones** — `get_player_cumulative_score` sums all scores including `is_legacy = 1` rows. A player whose legacy seed score is high could hit a milestone incorrectly. Add `AND is_legacy = 0` to that query.

- [ ] **`_INITIAL_TOP3` in `scheduler.py` uses old seed usernames** — hardcoded as `pitystomper69 / chicken__man. / Zach Coury`. If the DB is ever reset, startup shakeup detection will compare against the wrong names. Replace with a DB query for the actual seeded values, or remove the hardcoded fallback entirely now that `last_top3` is always written to `bot_config` after any shakeup.

- [ ] **`/admin reset` leaves `last_top3` stale** — `bot_config` is not cleared by the reset command. After a reset, `last_top3` still holds the old top-3, so the next startup shakeup check will compare against wrong data. Either clear `bot_config` on reset (except `score_channel_id`), or clear just `last_top3`.

- [ ] **Handicap group average includes players who haven't posted today** — `_build_handicap_embed` computes `group_avg` from all qualifying players' 30-day rolling avgs, then filters to only those who posted today. A player who skipped today still shifts the group avg but doesn't appear in results, skewing everyone else's adjusted score.

## Fragile / Cleanup

- [ ] **`SETUP.md` Step 7 shows a stale `seed_score` API** — the example call includes `game_date` and `round_scores` params that no longer exist in the current `seed_score(discord_id, username, final_score)` signature. Update the example to match.

- [ ] **`seed.py` still references old legacy usernames** — not used in production (seeding happens in `bot.py`), but the file would mislead anyone who runs it directly thinking it's current. Either delete it or update it to match the `_seed_legacy_scores` logic in `bot.py`.

- [ ] **`get_all_time_leaderboard` includes players with zero real scores** — the `LEFT JOIN` without an `is_legacy = 0` filter means a player who only has a legacy seed row (and has never played live) appears in the all-time leaderboard with `best_score = legacy_score`. This is intentional for pre-bot scores, but worth confirming it won't produce odd results as more players join.
