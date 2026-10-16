import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from config import mt_today

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Matches:
#   www.maptap.gg July 20
#   88🎉 96🔥 97🔥 97😱 7😱
#   Final score: 690
_PATTERN = re.compile(
    r"www\.maptap\.gg\s+(\w+)\s+(\d{1,2})\s*[\r\n]+"
    r"(\d{1,3})\S*\s+(\d{1,3})\S*\s+(\d{1,3})\S*\s+(\d{1,3})\S*\s+(\d{1,3})\S*\s*[\r\n]+"
    r"Final score:\s*(\d+)",
    re.IGNORECASE,
)


@dataclass
class ParsedScore:
    game_date: str          # YYYY-MM-DD
    round_scores: list[int] # [r1, r2, r3, r4, r5]
    final_score: int


def parse_maptap_share(text: str) -> Optional[ParsedScore]:
    m = _PATTERN.search(text)
    if not m:
        return None

    month_str = m.group(1).lower()
    month = MONTHS.get(month_str)
    if not month:
        return None

    day = int(m.group(2))
    round_scores = [int(m.group(i)) for i in range(3, 8)]
    final_score = int(m.group(8))

    # Validate round scores are in range
    if not all(0 <= r <= 100 for r in round_scores):
        return None

    # Use current year; if the month+day would be in the future, use previous year
    today = mt_today()
    year = today.year
    try:
        game_date = date(year, month, day)
    except ValueError:
        return None

    if game_date > today:
        game_date = date(year - 1, month, day)

    return ParsedScore(
        game_date=game_date.isoformat(),
        round_scores=round_scores,
        final_score=final_score,
    )


def looks_like_maptap(text: str) -> bool:
    """Quick check — does this text contain the MapTap header at all?"""
    return "maptap.gg" in text.lower()
