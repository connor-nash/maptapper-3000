import aiosqlite
import json
import os
from datetime import date, datetime
from typing import Optional

DB_PATH = os.environ.get("DB_PATH", "maptap.db")


async def _fetchone(db: aiosqlite.Connection, sql: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
    cursor = await db.execute(sql, params)
    return await cursor.fetchone()


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL REFERENCES players(id),
                game_date TEXT NOT NULL,
                round_scores TEXT NOT NULL,
                final_score INTEGER NOT NULL,
                is_legacy INTEGER NOT NULL DEFAULT 0,
                posted_at TEXT DEFAULT (datetime('now')),
                UNIQUE(player_id, game_date)
            );

            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL REFERENCES players(id),
                achievement_type TEXT NOT NULL,
                period TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS summaries_posted (
                summary_type TEXT NOT NULL,
                period TEXT NOT NULL,
                posted_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (summary_type, period)
            );

            CREATE TABLE IF NOT EXISTS bot_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        await db.commit()


# --- Player ---

async def upsert_player(discord_id: str, username: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "INSERT INTO players (discord_id, username) VALUES (?, ?) "
            "ON CONFLICT(discord_id) DO UPDATE SET username = excluded.username",
            (discord_id, username)
        )
        await db.commit()
        row = await _fetchone(db, "SELECT id FROM players WHERE discord_id = ?", (discord_id,))
        return row["id"]


async def get_player_by_discord_id(discord_id: str) -> Optional[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await _fetchone(db, "SELECT * FROM players WHERE discord_id = ?", (discord_id,))


async def get_all_players() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM players ORDER BY username")
        return await cursor.fetchall()


# --- Scores ---

async def insert_score(player_id: int, game_date: str, round_scores: list[int], final_score: int, is_legacy: bool = False) -> bool:
    """Returns True if inserted, False if already exists (first post wins)."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO scores (player_id, game_date, round_scores, final_score, is_legacy) VALUES (?, ?, ?, ?, ?)",
                (player_id, game_date, json.dumps(round_scores), final_score, 1 if is_legacy else 0)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_score(player_id: int, game_date: str) -> Optional[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await _fetchone(db, "SELECT * FROM scores WHERE player_id = ? AND game_date = ?", (player_id, game_date))


async def get_scores_for_date(game_date: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT s.*, p.discord_id, p.username
               FROM scores s JOIN players p ON s.player_id = p.id
               WHERE s.game_date = ? AND s.is_legacy = 0
               ORDER BY s.final_score DESC""",
            (game_date,)
        )
        return await cursor.fetchall()


def _iso_week_date_range(iso_year: int, iso_week: int) -> tuple[str, str]:
    import datetime as _dt
    jan4 = _dt.date(iso_year, 1, 4)
    week_start = jan4 + _dt.timedelta(weeks=iso_week - 1) - _dt.timedelta(days=jan4.isoweekday() - 1)
    week_end = week_start + _dt.timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()


async def get_scores_for_week(iso_year: int, iso_week: int) -> list:
    start, end = _iso_week_date_range(iso_year, iso_week)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT s.*, p.discord_id, p.username
               FROM scores s JOIN players p ON s.player_id = p.id
               WHERE s.game_date BETWEEN ? AND ? AND s.is_legacy = 0
               ORDER BY s.game_date, s.final_score DESC""",
            (start, end)
        )
        return await cursor.fetchall()


async def get_scores_for_month(year: int, month: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        prefix = f"{year:04d}-{month:02d}"
        cursor = await db.execute(
            """SELECT s.*, p.discord_id, p.username
               FROM scores s JOIN players p ON s.player_id = p.id
               WHERE s.game_date LIKE ? AND s.is_legacy = 0
               ORDER BY s.game_date, s.final_score DESC""",
            (f"{prefix}%",)
        )
        return await cursor.fetchall()


async def get_player_scores(player_id: int, limit: int = 30) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM scores WHERE player_id = ? ORDER BY game_date DESC LIMIT ?",
            (player_id, limit)
        )
        return await cursor.fetchall()


async def get_player_all_scores(player_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM scores WHERE player_id = ? AND is_legacy = 0 ORDER BY game_date",
            (player_id,)
        )
        return await cursor.fetchall()


async def get_player_cumulative_score(player_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await _fetchone(db, "SELECT COALESCE(SUM(final_score), 0) as total FROM scores WHERE player_id = ?", (player_id,))
        return row[0] if row else 0


async def get_player_perfect_rounds_count(player_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT round_scores FROM scores WHERE player_id = ? AND is_legacy = 0",
            (player_id,)
        )
        rows = await cursor.fetchall()
        count = 0
        for row in rows:
            rounds = json.loads(row["round_scores"])
            count += sum(1 for r in rounds if r == 100)
        return count


async def get_player_fumble_count(player_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await _fetchone(db,
            "SELECT COUNT(*) FROM achievements WHERE player_id = ? AND achievement_type = 'fumble'",
            (player_id,)
        )
        return row[0] if row else 0


async def get_all_time_leaderboard() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT p.discord_id, p.username,
                      COALESCE(SUM(s.final_score), 0) as total,
                      COUNT(s.id) as games_played,
                      COALESCE(AVG(s.final_score), 0) as avg_score,
                      COALESCE(MAX(s.final_score), 0) as best_score
               FROM players p
               LEFT JOIN scores s ON s.player_id = p.id
               GROUP BY p.id
               ORDER BY total DESC"""
        )
        return await cursor.fetchall()


async def get_player_rolling_avg(player_id: int, days: int = 30) -> Optional[float]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await _fetchone(db,
            "SELECT AVG(final_score) FROM scores WHERE player_id = ? AND is_legacy = 0 AND game_date >= date('now', ?)",
            (player_id, f"-{days} days")
        )
        return row[0] if row and row[0] is not None else None


# --- Config ---

async def get_config(key: str) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await _fetchone(db, "SELECT value FROM bot_config WHERE key = ?", (key,))
        return row[0] if row else None


async def set_config(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bot_config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )
        await db.commit()


# --- Summaries ---

async def mark_summary_posted(summary_type: str, period: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO summaries_posted (summary_type, period) VALUES (?, ?)",
            (summary_type, period)
        )
        await db.commit()


async def is_summary_posted(summary_type: str, period: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await _fetchone(db,
            "SELECT 1 FROM summaries_posted WHERE summary_type = ? AND period = ?",
            (summary_type, period)
        )
        return row is not None


# --- Achievements ---

async def record_achievement(player_id: int, achievement_type: str, period: str, metadata: dict = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO achievements (player_id, achievement_type, period, metadata) VALUES (?, ?, ?, ?)",
            (player_id, achievement_type, period, json.dumps(metadata) if metadata else None)
        )
        await db.commit()


async def has_achievement(player_id: int, achievement_type: str, period: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await _fetchone(db,
            "SELECT 1 FROM achievements WHERE player_id = ? AND achievement_type = ? AND period = ?",
            (player_id, achievement_type, period)
        )
        return row is not None


async def get_player_achievements(player_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM achievements WHERE player_id = ? ORDER BY created_at DESC",
            (player_id,)
        )
        return await cursor.fetchall()


# --- Weekly / Monthly helpers ---

async def compute_weekly_scores(iso_year: int, iso_week: int) -> list[dict]:
    all_scores = await get_scores_for_week(iso_year, iso_week)

    player_scores: dict[str, dict] = {}
    for row in all_scores:
        pid = row["discord_id"]
        if pid not in player_scores:
            player_scores[pid] = {"discord_id": row["discord_id"], "username": row["username"], "daily_scores": []}
        player_scores[pid]["daily_scores"].append(row["final_score"])

    results = []
    for pid, data in player_scores.items():
        daily = data["daily_scores"]
        padded = sorted(daily + [0] * (7 - len(daily)))
        kept = padded[2:]
        results.append({
            "discord_id": data["discord_id"],
            "username": data["username"],
            "weekly_score": sum(kept),
            "games_played": len(daily),
        })

    all_players = await get_all_players()
    existing_ids = {r["discord_id"] for r in results}
    for p in all_players:
        if p["discord_id"] not in existing_ids and not p["discord_id"].startswith("seed:"):
            results.append({"discord_id": p["discord_id"], "username": p["username"], "weekly_score": 0, "games_played": 0})

    results.sort(key=lambda x: x["weekly_score"], reverse=True)
    return results


async def compute_monthly_scores(year: int, month: int) -> list[dict]:
    all_scores = await get_scores_for_month(year, month)

    player_data: dict[str, dict] = {}
    for row in all_scores:
        pid = row["discord_id"]
        if pid not in player_data:
            player_data[pid] = {"discord_id": row["discord_id"], "username": row["username"], "monthly_total": 0, "games_played": 0}
        player_data[pid]["monthly_total"] += row["final_score"]
        player_data[pid]["games_played"] += 1

    results = list(player_data.values())
    results.sort(key=lambda x: x["monthly_total"], reverse=True)
    return results


async def get_player_month_game_count(player_id: int, year: int, month: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        prefix = f"{year:04d}-{month:02d}"
        row = await _fetchone(db,
            "SELECT COUNT(*) FROM scores WHERE player_id = ? AND game_date LIKE ? AND is_legacy = 0",
            (player_id, f"{prefix}%")
        )
        return row[0] if row else 0


async def get_player_prev_month_avg(player_id: int, year: int, month: int) -> Optional[float]:
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    prefix = f"{prev_year:04d}-{prev_month:02d}"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await _fetchone(db,
            "SELECT AVG(final_score) FROM scores WHERE player_id = ? AND game_date LIKE ? AND is_legacy = 0",
            (player_id, f"{prefix}%")
        )
        return row[0] if row and row[0] is not None else None


async def get_player_current_month_avg(player_id: int, year: int, month: int) -> Optional[float]:
    prefix = f"{year:04d}-{month:02d}"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await _fetchone(db,
            "SELECT AVG(final_score) FROM scores WHERE player_id = ? AND game_date LIKE ? AND is_legacy = 0",
            (player_id, f"{prefix}%")
        )
        return row[0] if row and row[0] is not None else None


# --- Seeding / Linking ---

async def seed_score(discord_id: str, username: str, final_score: int):
    """Seed a legacy score (all-time leaderboard only, excluded from weekly/monthly)."""
    player_id = await upsert_player(discord_id, username)
    game_date = f"2000-01-{(player_id % 28) + 1:02d}"
    await insert_score(player_id, game_date, [0, 0, 0, 0, 0], final_score, is_legacy=True)


async def link_player(username: str, real_discord_id: str) -> bool:
    """Link a seeded player to their real Discord ID, merging their history."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        seed_row = await _fetchone(db,
            "SELECT id FROM players WHERE username = ? AND discord_id LIKE 'seed:%'",
            (username,)
        )
        if seed_row is None:
            return False
        seeded_id = seed_row["id"]

        existing = await _fetchone(db, "SELECT id FROM players WHERE discord_id = ?", (real_discord_id,))
        if existing:
            await db.execute("UPDATE scores SET player_id = ? WHERE player_id = ?", (existing["id"], seeded_id))
            await db.execute("UPDATE achievements SET player_id = ? WHERE player_id = ?", (existing["id"], seeded_id))
            await db.execute("DELETE FROM players WHERE id = ?", (seeded_id,))
        else:
            await db.execute("UPDATE players SET discord_id = ? WHERE id = ?", (real_discord_id, seeded_id))

        await db.commit()
        return True
