import asyncio
from copy import copy

import discord
import pytest

import database as db
from cogs.listener import Listener
from cogs.scheduler import Scheduler


class FakeMember:
    def __init__(self, member_id: int, nick: str | None = None, guild=None, forbid_edit: bool = False):
        self.id = member_id
        self.nick = nick
        self.guild = guild
        self.forbid_edit = forbid_edit
        self.edits: list[str | None] = []

    async def edit(self, *, nick: str | None):
        if self.forbid_edit:
            raise discord.Forbidden(type("Resp", (), {"status": 403, "reason": "Forbidden"})(), "Missing Permissions")
        self.edits.append(nick)
        before = copy(self)
        self.nick = nick
        if self.guild and self.guild.listener:
            await self.guild.listener.on_member_update(before, self)


class FakeChannel:
    def __init__(self):
        self.messages: list[str] = []

    async def send(self, content: str = "", **_):
        self.messages.append(content)


class FakeGuild:
    def __init__(self, members: list[FakeMember], listener: Listener | None = None):
        self.members = {m.id: m for m in members}
        self.listener = listener
        for m in members:
            m.guild = self

    def get_member(self, member_id: int) -> FakeMember | None:
        return self.members.get(member_id)


class FakeBot:
    def __init__(self, channel: FakeChannel):
        self.channel = channel

    def get_channel(self, _):
        return self.channel


@pytest.fixture
def bungus_env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    asyncio.run(db.init_db())
    asyncio.run(db.set_config("score_channel_id", "999"))
    channel = FakeChannel()
    bot = FakeBot(channel)
    listener = Listener(bot)
    scheduler = Scheduler.__new__(Scheduler)
    scheduler.bot = bot
    return scheduler, listener, channel


async def _seed_week_score(discord_id: str, username: str, game_date: str, final_score: int):
    pid = await db.upsert_player(discord_id, username)
    await db.insert_score(pid, game_date, [50, 50, 50, 50, 50], final_score)


def test_crowns_lowest_scorer_and_sets_config(bungus_env):
    scheduler, listener, channel = bungus_env
    m1, m2 = FakeMember(111), FakeMember(222)
    guild = FakeGuild([m1, m2], listener)

    async def go():
        await _seed_week_score("111", "Alice", "2026-11-10", 820)
        await _seed_week_score("222", "Bob", "2026-11-12", 508)
        await scheduler._crown_bungus_jones(guild, 2026, 46)
        assert await db.get_config("current_bungus_id") == "222"

    asyncio.run(go())
    assert m2.nick == "Bungus Jones"
    assert m1.nick is None
    assert channel.messages == []


def test_handover_to_new_bungus_does_not_trigger_escape_listener(bungus_env):
    # Regression test: previously, clearing the old Bungus's nick fired BEFORE
    # current_bungus_id was updated, causing on_member_update to re-rename the old
    # Bungus back to "Bungus Jones" and post "No." in the channel!
    scheduler, listener, channel = bungus_env
    old_bungus = FakeMember(111, nick="Bungus Jones")
    new_bungus = FakeMember(222, nick=None)
    guild = FakeGuild([old_bungus, new_bungus], listener)

    async def go():
        await db.set_config("current_bungus_id", "111")
        await _seed_week_score("111", "Alice", "2026-11-10", 900)
        await _seed_week_score("222", "Bob", "2026-11-12", 450)
        await scheduler._crown_bungus_jones(guild, 2026, 46)

    asyncio.run(go())
    assert old_bungus.nick is None
    assert old_bungus.edits == [None]
    assert new_bungus.nick == "Bungus Jones"
    assert channel.messages == []


def test_escape_attempt_reverts_nickname_and_posts_no(bungus_env):
    _, listener, channel = bungus_env
    victim = FakeMember(222, nick="Bungus Jones")
    FakeGuild([victim], listener)

    async def go():
        await db.set_config("current_bungus_id", "222")
        before = copy(victim)
        victim.nick = "Real Name"
        await listener.on_member_update(before, victim)

    asyncio.run(go())
    assert victim.nick == "Bungus Jones"
    assert channel.messages == ["No."]


def test_forbidden_on_server_owner_does_not_crash(bungus_env):
    scheduler, listener, channel = bungus_env
    owner = FakeMember(222, forbid_edit=True)
    guild = FakeGuild([owner], listener)

    async def go():
        await _seed_week_score("222", "Owner", "2026-11-12", 400)
        await scheduler._crown_bungus_jones(guild, 2026, 46)

    asyncio.run(go())
    assert owner.nick is None
