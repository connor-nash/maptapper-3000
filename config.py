import pytz
from datetime import datetime, time

TIMEZONE = pytz.timezone("America/Denver")  # Mountain Time
SUMMARY_HOUR = 7
SUMMARY_MINUTE = 0


def mt_today():
    return datetime.now(TIMEZONE).date()

EMBED_COLOR = 0x2ECC71  # Green

MAPTAP_URL = "https://www.maptap.gg"

# Round weights: rounds 1-5
ROUND_WEIGHTS = [1, 1, 2, 3, 3]
ROUND_MAX_WEIGHTED = sum(w * 100 for w in ROUND_WEIGHTS)  # 1000

# Fumble threshold: if the projected score (replacing worst round with avg of others) >= this,
# it's a Fumble
FUMBLE_PROJECTED_THRESHOLD = 960

# Cliff threshold: point drop from previous score that triggers the Cliff achievement
CLIFF_DROP_THRESHOLD = 200

# Milestone thresholds (cumulative total score)
SCORE_MILESTONES = [100_000, 250_000, 500_000, 1_000_000]

# Milestone thresholds (cumulative perfect rounds, i.e. round score == 100)
PERFECT_ROUND_MILESTONES = [100, 200, 300, 500]

# Number of daily slots per week (Mon-Sun)
WEEK_DAYS = 7
# Number of scores to drop each week
WEEK_DROPS = 2

# Number of lowest scores to drop each month (fixed regardless of month length)
MONTH_DROPS = 8

# Handicap rolling window in days
HANDICAP_WINDOW_DAYS = 30

# Minimum games played before a player appears in the handicap leaderboard
MIN_HANDICAP_GAMES = 5
