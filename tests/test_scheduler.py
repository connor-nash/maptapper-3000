import asyncio
from datetime import date

import pytest

import database as db
import cogs.scheduler as scheduler_mod
from cogs.scheduler import Scheduler


class FakeChannel:
    def __init__(self, fail_titles=()):
        self.fail_titles = fail_titles
        self.sent = []
        self.guild = None

    async def send(self, embed=None, **_):
        if any(t in embed.title for t in self.fail_titles):
            raise RuntimeError("Discord said no")
        self.sent.append(embed.title)


class FakeBot:
    def __init__(self, channel):
        self.channel = channel

    def get_channel(self, _):
        return self.channel


def make_scheduler(channel) -> Scheduler:
    sched = Scheduler.__new__(Scheduler)
    sched.bot = FakeBot(channel)
    return sched


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))

    async def no_crowning(*_):
        pass
    monkeypatch.setattr(Scheduler, "_crown_bungus_jones", no_crowning)

    def run(today: date, channel: FakeChannel):
        monkeypatch.setattr(scheduler_mod, "mt_today", lambda: today)

        async def go():
            await db.init_db()
            await db.set_config("score_channel_id", "123")
            await make_scheduler(channel)._post_pending_summaries()
        asyncio.run(go())
    return run


def posted(summary_type, period):
    return asyncio.run(db.is_summary_posted(summary_type, period))


def test_failed_daily_does_not_block_weekly_or_monthly(setup):
    channel = FakeChannel(fail_titles=("Daily",))
    setup(date(2026, 12, 1), channel)

    assert not posted("daily", "2026-11-30")
    assert posted("weekly", "2026-W48")
    assert posted("monthly", "2026-11")
    assert any("Weekly" in t for t in channel.sent)
    assert any("Monthly" in t for t in channel.sent)


def test_failed_daily_retries_next_run(setup):
    setup(date(2026, 12, 1), FakeChannel(fail_titles=("Daily",)))
    channel = FakeChannel()
    setup(date(2026, 12, 1), channel)

    assert posted("daily", "2026-11-30")
    assert len(channel.sent) == 1


def test_missed_monday_weekly_still_posts_on_tuesday(setup):
    channel = FakeChannel()
    setup(date(2026, 11, 17), channel)

    assert posted("weekly", "2026-W46")


def test_nothing_reposts_once_marked(setup):
    setup(date(2026, 11, 17), FakeChannel())
    channel = FakeChannel()
    setup(date(2026, 11, 17), channel)

    assert channel.sent == []
