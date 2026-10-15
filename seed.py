"""
Run once to seed legacy scores before the bot was live.
These appear on the all-time leaderboard only.
"""
import asyncio
from database import init_db, seed_score

LEGACY_SCORES = [
    ("seed:pitystomper69", "pitystomper69", 990),
    ("seed:chicken__man.",  "chicken__man.",  984),
    ("seed:Zach Coury",     "Zach Coury",     969),
]

async def main():
    await init_db()
    for discord_id, username, final_score in LEGACY_SCORES:
        await seed_score(discord_id, username, final_score)
        print(f"Seeded {username}: {final_score}")
    print("Done.")

asyncio.run(main())
