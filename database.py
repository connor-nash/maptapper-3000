import aiosqlite
import json
from datetime import date, datetime
from typing import Optional
import pytz
from config import TIMEZONE

import os
DB_PATH = os.environ.get("DB_PATH", "maptap.db")


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
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
        row = await db.execute_fetchone("SELECT id FROM players WHERE discord_id = ?", (discord_id,))
        return row["id"]


async def get_player_by_discord_id(discord_id: str) -> Optional[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await db.execute_fetchone(
            "SELECT * FROM players WHERE discord_id = ?", (discord_id,)
        )


async def get_all_players() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM players ORDER BY username")
        return await cursor.fetchall()


# --- Scores ---

async def insert_score(player_id: int, game_date: str, round_scores: list[int], final_score: int) -> bool:
    """Returns True if inserted, False if already exists (first post wins)."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO scores (player_id, game_date, round_scores, final_score) VALUES (?, ?, ?, ?)",
                (player_id, game_date, json.dumps(round_scores), final_score)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_score(player_id: int, game_date: str) -> Optional[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await db.execute_fetchone(
            "SELECT * FROM scores WHERE player_id = ? AND game_date = ?",
            (player_id, game_date)
        )


async def get_scores_for_date(game_date: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT s.*, p.discord_id, p.username
               FROM scores s JOIN players p ON s.player_id = p.id
               WHERE s.game_date = ?
               ORDER BY s.final_score DESC""",
            (game_date,)
        )
        return await cursor.fetchall()


def _iso_week_date_range(iso_year: int, iso_week: int) -> tuple[str, str]:
    """Returns (monday_str, sunday_str) for a given ISO year+week."""
    import datetime as _dt
    jan4 = _dt.date(iso_year, 1, 4)
    week_start = jan4 + _dt.timedelta(weeks=iso_week - 1) - _dt.timedelta(days=jan4.isoweekday() - 1)
    week_end = week_start + _dt.timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()


async def get_scores_for_week(iso_year: int, iso_week: int) -> list:
    """Returns all scores for a given ISO week (Mon-Sun)."""
    start, end = _iso_week_date_range(iso_year, iso_week)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT s.*, p.discord_id, p.username
               FROM scores s JOIN players p ON s.player_id = p.id
               WHERE s.game_date BETWEEN ? AND ?
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
               WHERE s.game_date LIKE ?
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
            "SELECT * FROM scores WHERE player_id = ? ORDER BY game_date",
            (player_id,)
        )
        return await cursor.fetchall()


async def get_player_cumulative_score(player_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchone(
            "SELECT COALESCE(SUM(final_score), 0) as total FROM scores WHERE player_id = ?",
            (player_id,)
        )
        return row[0] if row else 0


async def get_player_perfect_rounds_count(player_id: int) -> int:
    """Count how many individual rounds scored exactly 100."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT round_scores FROM scores WHERE player_id = ?",
            (player_id,)
        )
        rows = await cursor.fetchall()
        count = 0
        for row in rows:
            rounds = json.loads(row["round_scores"])
            count += sum(1 for r in rounds if r == 100)
        return count


async def get_player_fumble_count(player_id: int) -> int:
    """Count achievements of type 'fumble' for a player."""
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchone(
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
        row = await db.execute_fetchone(
            """SELECT AVG(final_score) FROM scores
               WHERE player_id = ?
               AND game_date >= date('now', ?)""",
            (player_id, f"-{days} days")
        )
        return row[0] if row and row[0] is not None else None


# --- Config ---

async def get_config(key: str) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchone("SELECT value FROM bot_config WHERE key = ?", (key,))
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
        row = await db.execute_fetchone(
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
        row = await db.execute_fetchone(
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


# --- Weekly leaderboard helpers ---

async def compute_weekly_scores(iso_year: int, iso_week: int) -> list[dict]:
    """
    Returns weekly scores per player using the drop-2 mechanic.
    Each week has 7 slots (Mon-Sun). Unplayed days = 0.
    Drop the 2 lowest scores, sum the remaining 5.
    """
    all_scores = await get_scores_for_week(iso_year, iso_week)

    # Group by player
    player_scores: dict[str, dict] = {}
    for row in all_scores:
        pid = row["discord_id"]
        if pid not in player_scores:
            player_scores[pid] = {
                "discord_id": row["discord_id"],
                "username": row["username"],
                "daily_scores": [],
            }
        player_scores[pid]["daily_scores"].append(row["final_score"])

    results = []
    for pid, data in player_scores.items():
        daily = data["daily_scores"]
        # Pad to 7 with zeros for missed days
        padded = daily + [0] * (7 - len(daily))
        padded.sort()
        # Drop 2 lowest
        kept = padded[2:]
        results.append({
            "discord_id": data["discord_id"],
            "username": data["username"],
            "weekly_score": sum(kept),
            "games_played": len(daily),
            "raw_scores": daily,
        })

    # Include players who played nothing this week
    all_players = await get_all_players()
    existing_ids = {r["discord_id"] for r in results}
    for p in all_players:
        if p["discord_id"] not in existing_ids:
            results.append({
                "discord_id": p["discord_id"],
                "username": p["username"],
                "weekly_score": 0,
                "games_played": 0,
                "raw_scores": [],
            })

    results.sort(key=lambda x: x["weekly_score"], reverse=True)
    return results


async def compute_monthly_scores(year: int, month: int) -> list[dict]:
    """Returns total monthly scores per player."""
    all_scores = await get_scores_for_month(year, month)

    player_data: dict[str, dict] = {}
    for row in all_scores:
        pid = row["discord_id"]
        if pid not in player_data:
            player_data[pid] = {
                "discord_id": row["discord_id"],
                "username": row["username"],
                "monthly_total": 0,
                "games_played": 0,
            }
        player_data[pid]["monthly_total"] += row["final_score"]
        player_data[pid]["games_played"] += 1

    results = list(player_data.values())
    results.sort(key=lambda x: x["monthly_total"], reverse=True)
    return results


async def get_days_in_month(year: int, month: int) -> int:
    import calendar
    return calendar.monthrange(year, month)[1]


async def get_player_month_game_count(player_id: int, year: int, month: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        prefix = f"{year:04d}-{month:02d}"
        row = await db.execute_fetchone(
            "SELECT COUNT(*) FROM scores WHERE player_id = ? AND game_date LIKE ?",
            (player_id, f"{prefix}%")
        )
        return row[0] if row else 0


async def get_player_prev_month_avg(player_id: int, year: int, month: int) -> Optional[float]:
    """Get a player's average score for the month before (year, month)."""
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    prefix = f"{prev_year:04d}-{prev_month:02d}"
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchone(
            "SELECT AVG(final_score) FROM scores WHERE player_id = ? AND game_date LIKE ?",
            (player_id, f"{prefix}%")
        )
        return row[0] if row and row[0] is not None else None


async def get_player_current_month_avg(player_id: int, year: int, month: int) -> Optional[float]:
    prefix = f"{year:04d}-{month:02d}"
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchone(
            "SELECT AVG(final_score) FROM scores WHERE player_id = ? AND game_date LIKE ?",
            (player_id, f"{prefix}%")
        )
        return row[0] if row and row[0] is not None else None


async def seed_score(discord_id: str, username: str, game_date: str, round_scores: list[int], final_score: int):
    """Used for seeding initial historical data."""
    player_id = await upsert_player(discord_id, username)
    await insert_score(player_id, game_date, round_scores, final_score)
