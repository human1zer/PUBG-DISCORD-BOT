# 🎮 PUBG Discord Bot

A fully async Python Discord bot that automatically tracks PUBG matches for a list of players and posts rich stat embeds to your Discord server — with weekly leaderboards and live player management.

---

## Features

- **Auto match tracking** — polls the PUBG API on a configurable interval and posts new matches to Discord
- **Rich embeds** — detailed per-player stats including kills, damage, headshots, longest kill, survival time, heals/boosts, and more
- **No duplicate posts** — match IDs are persisted to `posted_matches.json` so restarts never cause double-posting
- **Group match detection** — if multiple tracked players were in the same match, it posts only one combined embed
- **Weekly summaries** — every Wednesday at 18:00 UTC the bot automatically posts a weekly best-of summary, leaderboard, and all-time longest kills embed
- **Dynamic player management** — add or remove players at runtime via Discord commands without restarting the bot
- **Match categorization** — correctly labels `airoyale` matches as **CASUAL** and `official` matches as **NORMAL**
- **Persistent history** — weekly stats accumulate across restarts; posted match history is capped at 200 entries

---

## Project Structure

```
PUBG-DISCORD-BOOT/
├── Main.py                  # Entry point — loads config & starts the bot
├── bot.py                   # Core bot class, Discord commands, polling loop
├── tracker.py               # Async PUBG API client & match fetching logic
├── embeds.py                # Discord embed builder (rich match cards)
├── weekly_stats.py          # Weekly stats aggregation & leaderboard embeds
├── scrape_longest_kills.py  # One-time scraper to seed all-time longest kills data
├── players.txt              # List of PUBG player names to track (one per line)
└── config.json              # API keys, channel IDs, and timing settings (auto-created)
```

---

## Requirements

- Python 3.9+
- A [PUBG Developer API key](https://developer.pubg.com/)
- A Discord bot token

Install dependencies:

```bash
pip install discord.py aiohttp
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/human1zer/PUBG-DISCORD-BOOT.git
cd PUBG-DISCORD-BOOT
```

### 2. Get a PUBG API key

Go to [https://developer.pubg.com/](https://developer.pubg.com/), sign in, and create an app to get your API key.

### 3. Create a Discord bot

1. Go to [https://discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** and give it a name
3. Go to the **Bot** tab → click **Add Bot**
4. Copy the **bot token**
5. Under **Privileged Gateway Intents**, enable **Message Content Intent**
6. Go to **OAuth2 → URL Generator**, select the `bot` scope and `Send Messages` + `Embed Links` permissions
7. Open the generated URL in your browser to invite the bot to your server
8. Right-click the target channel → **Copy ID** (requires Developer Mode in Discord settings)

### 4. Configure `config.json`

Run `python Main.py` once — it will auto-create `config.json`. Then fill in your values:

```json
{
  "pubg_api_key": "your-pubg-api-key",
  "discord_token": "your-discord-bot-token",
  "discord_channel_id": 123456789012345678,
  "weekly_channel_id": 123456789012345678,
  "check_interval_seconds": 150,
  "request_delay": 7.0,
  "max_retries": 3
}
```

| Field | Description |
|---|---|
| `pubg_api_key` | Your PUBG Developer API key |
| `discord_token` | Your Discord bot token |
| `discord_channel_id` | Channel to post match results |
| `weekly_channel_id` | Channel for weekly summaries (defaults to `discord_channel_id`) |
| `check_interval_seconds` | How often to poll for new matches (default: 150s) |
| `request_delay` | Delay between API requests per player (default: 7.0s) |
| `max_retries` | API retry attempts on failure (default: 3) |

### 5. Add players to `players.txt`

One player name per line. Lines starting with `#` are ignored.

```
# My squad
PlayerOne
PlayerTwo
PlayerThree
```

### 6. (Optional) Seed all-time longest kills data

```bash
python scrape_longest_kills.py
```

This populates the data needed for the all-time longest kills embed in weekly summaries.

### 7. Run the bot

```bash
python Main.py
```

---

## Discord Commands

All commands require **Administrator** permission except `!listplayers`.

| Command | Description |
|---|---|
| `!addplayer <name>` | Add a player to the tracking list |
| `!removeplayer <name>` | Remove a player from the tracking list |
| `!listplayers` | Show all currently tracked players |
| `!weeklynow` | Manually trigger the weekly summary post |
| `!testpost [name]` | Generate a test embed and save it to `test_embed.txt` |

---

## Weekly Summaries

The bot automatically posts three embeds every **Wednesday at 18:00 UTC**:

1. **Best Player of the Week** — highlights the top performer across key stats
2. **Leaderboard** — ranked top 5 players by kills/performance over the last 7 days
3. **All-Time Longest Kills** — requires running `scrape_longest_kills.py` first

You can trigger this manually anytime with `!weeklynow`.

---

## Notes

- All players are tracked on the **Steam** platform. Console platforms are not currently supported.
- The bot deduplicates matches across players — if two tracked players played together, only one embed is posted.
- `posted_matches.json` is auto-managed and capped at 200 entries to avoid unbounded growth.
- The `players.txt` file is updated live when using `!addplayer` / `!removeplayer`.
