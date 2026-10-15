# MapTapper 3000 — Setup Guide

## Step 1: Create the Discord Application

1. Go to https://discord.com/developers/applications
2. Click **New Application** → name it "MapTapper 3000"
3. Go to the **Bot** tab on the left
4. Click **Add Bot** → confirm
5. Under **Privileged Gateway Intents**, enable:
   - ✅ **Message Content Intent** (required to read score pastes)
6. Click **Save Changes**
7. Click **Reset Token** → copy and save the token — you'll need this (treat it like a password)

## Step 2: Invite the Bot to Your Server

1. Go to the **OAuth2 → URL Generator** tab
2. Under **Scopes**, check:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Under **Bot Permissions**, check:
   - ✅ Read Messages/View Channels
   - ✅ Send Messages
   - ✅ Embed Links
   - ✅ Add Reactions
   - ✅ Read Message History
4. Copy the generated URL at the bottom and open it in your browser
5. Select your server and authorize

## Step 3: Install Python (if needed)

You need Python 3.12+. Check: `python3 --version`

If not installed: https://www.python.org/downloads/

## Step 4: Set Up the Bot Locally

```bash
# Navigate to the project folder
cd /path/to/MapTap_Tracker

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create your .env file
cp env.example .env
# Open .env and paste your bot token:
# DISCORD_TOKEN=your_token_here
```

## Step 5: Run the Bot

```bash
python bot.py
```

You should see:
```
Synced slash commands.
MapTapper 3000 online as MapTapper 3000#XXXX (123456789)
```

## Step 6: Configure the Score Channel in Discord

In your Discord server, run this slash command (you need Administrator):
```
/admin set-channel #your-maptap-channel
```

Done! Now when anyone pastes a MapTap share into that channel, the bot will parse it and track their score.

## Step 7: Seed Starting Data (Optional)

If you have existing scores to enter, use the `seed_score` function in a quick script:

```python
# seed.py — run once then delete
import asyncio
from database import seed_score, init_db

async def main():
    await init_db()
    # Format: discord_id, display_name, YYYY-MM-DD, [r1,r2,r3,r4,r5], final_score
    await seed_score("123456789", "PlayerOne", "2026-10-14", [88, 96, 97, 97, 7], 690)
    await seed_score("987654321", "PlayerTwo", "2026-10-14", [95, 92, 88, 80, 89], 872)
    print("Done!")

asyncio.run(main())
```

To get a player's Discord ID: right-click their name in Discord → Copy User ID
(You may need to enable Developer Mode: User Settings → Advanced → Developer Mode)

---

## Deploying to Fly.io (Free, Always-On)

### Prerequisites
- Create a free account at https://fly.io
- Install the Fly CLI: https://fly.io/docs/hands-on/install-flyctl/

```bash
# Log in
fly auth login

# From the project directory — first-time setup
fly launch --no-deploy
# When prompted for app name, enter: maptapper-3000
# Choose region: Denver (den) — closest to Mountain Time
# Say NO to Postgres, Redis, etc.

# Create a persistent volume for the SQLite database (1 GB, free)
fly volumes create maptap_data --size 1 --region den

# Add your bot token as a secret (never commit this to git)
fly secrets set DISCORD_TOKEN=your_token_here

# Deploy
fly deploy

# Check logs
fly logs
```

### Updating the Bot

```bash
# After making changes:
fly deploy
```

### Checking Status

```bash
fly status
fly logs
```

---

## Slash Commands Reference

| Command | Description |
|---|---|
| `/leaderboard` | Daily / weekly / monthly / all-time / ♿ handicap |
| `/mystats` | Your personal stats and fun facts |
| `/stats @user` | Look up another player |
| `/achievements` | Your trophy case |
| `/admin set-channel #channel` | Set the score listening channel (admin only) |
| `/admin status` | Check bot configuration (admin only) |
| `/admin reset confirm:yes` | Wipe all data (admin only, irreversible) |

---

## How Scoring Works

- **Daily**: raw final score from your share paste
- **Weekly** (Mon–Sun): 7 slots per week; missed days = 0; drop the 2 lowest; sum the remaining 5
- **Monthly**: sum of all daily scores for the month
- **♿ Handicap**: your score adjusted for your 30-day rolling average vs. the group average

## Achievements

| Achievement | When |
|---|---|
| 🎯 **Perfect Score** | Score 1000 — announced immediately |
| 🦃 **The Turkey** | Three 100s in one game — immediately |
| 🏆 **Score Milestones** | 100k / 250k / 500k cumulative points — immediately |
| 💯 **Perfect Round Milestones** | 100 / 200 / 300 / 500 total perfect rounds — immediately |
| 🫗 **Fumble** | One terrible round killed what would've been 960+ — daily summary |
| 👯 **Twinsies** | Exact same score as another player — daily summary |
| 🗺️ **I Think Yer Fuckin' Lost Bud** | Worst single round of the week — weekly summary |
| 📈 **Most Improved** | Biggest avg improvement vs. prior month — monthly summary |
| 🤪 **Get a Life** | Played every day of the calendar month — monthly summary |
| 🫧 **MIA** | Fewest games played that month — monthly summary |
