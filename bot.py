import discord
from discord.ext import tasks, commands
import json
import os
import asyncio
import traceback
from datetime import datetime, timezone
from typing import List, Tuple, Optional, Set
import logging

from tracker import AsyncPUBGMatchTracker
from embeds import create_enhanced_match_embed
from weekly_stats import WeeklyStatsManager

logger = logging.getLogger(__name__)


class IntegratedPUBGBot:
    """Enhanced PUBG Discord Bot with async architecture and dynamic player management"""
    
    def __init__(
        self, 
        discord_token: str,
        channel_id: int,
        api_key: str,
        players: List[Tuple[str, str]],
        check_interval: int = 300,
        request_delay: float = 7.0,
        max_retries: int = 3,
        weekly_channel_id: int = None
        
    ):
        self.discord_token = discord_token
        self.channel_id = channel_id
        self.weekly_channel_id = weekly_channel_id or channel_id
        self.players = players
        self.check_interval = check_interval
        self.players_file = "players.txt"
        
        self.tracker = AsyncPUBGMatchTracker(api_key, request_delay, max_retries)
        self.stats_manager = WeeklyStatsManager(max_history=1000)
        
        self.posted_matches = self.load_posted_matches()
        
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = commands.Bot(command_prefix='!', intents=intents)
        
        self.client.event(self.on_ready)
        self.register_commands()
        
        self.cycle_number = 1
        self.is_running = False
    
    def register_commands(self):
        """Register Discord bot commands"""
        
        @self.client.command(name='addplayer')
        async def add_player(ctx, player_name: str):
            """Add a new player to track — usage: !addplayer PlayerName"""
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("❌ Only administrators can add players!")
                return
        


            # Check if player already exists (case-insensitive)
            for existing_name, _ in self.players:
                if existing_name.lower() == player_name.lower():
                    await ctx.send(f"❌ Player `{player_name}` is already being tracked!")
                    return
            
        
        
            # All players use steam platform internally
            platform = 'steam'
            self.players.append((player_name, platform))
            
            try:
                with open(self.players_file, 'a', encoding='utf-8') as f:
                    # Write only the player name — no platform
                    f.write(f"\n{player_name}")
                
                await ctx.send(f"✅ Added `{player_name}` to tracking list!\n📋 Total players: {len(self.players)}")
                logger.info(f"✅ Added player: {player_name} — Total: {len(self.players)}")
            except Exception as e:
                await ctx.send(f"❌ Error saving player: {e}")
                self.players.remove((player_name, platform))
        
        @self.client.command(name='removeplayer')
        async def remove_player(ctx, player_name: str):
            """Remove a player from tracking — usage: !removeplayer PlayerName"""
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("❌ Only administrators can remove players!")
                return
            
            removed = False
            removed_platform = 'steam'
            for player, platform in self.players[:]:
                if player.lower() == player_name.lower():
                    self.players.remove((player, platform))
                    removed = True
                    removed_platform = platform
                    break
            
            if not removed:
                await ctx.send(f"❌ Player `{player_name}` not found in tracking list!")
                return
            
            try:
                self.save_players_to_file()
                await ctx.send(f"✅ Removed `{player_name}` from tracking!\n📋 Remaining players: {len(self.players)}")
                logger.info(f"❌ Removed player: {player_name} — Remaining: {len(self.players)}")
            except Exception as e:
                await ctx.send(f"❌ Error updating file: {e}")
                self.players.append((player_name, removed_platform))
        
        @self.client.command(name='listplayers')
        async def list_players(ctx):
            """List all tracked players"""
            if not self.players:
                await ctx.send("📋 No players are currently being tracked.")
                return
        
            
            embed = discord.Embed(
                title="📋 Tracked Players",
                description=f"Total: {len(self.players)}",
                color=discord.Color.blue()
            )
            
            # Show only names — no platform column
            players_text = ""
            for idx, (name, _) in enumerate(self.players, 1):
                players_text += f"{idx}. **{name}**\n"
            
            embed.add_field(name="Players", value=players_text, inline=False)
            await ctx.send(embed=embed)
             

        
        @self.client.command(name='testpost')
        async def test_post(ctx, player_name: str = None):
            """Test embed output to txt — usage: !testpost PlayerName"""

            if not player_name and self.players:
                player_name = self.players[0][0]
            elif not player_name:
                await ctx.send("❌ No players being tracked!")
                return

            fake_match = {
                "match_id": "test-match-id-000000000000",
                "match_category": "NORMAL",
                "game_mode": "squad",
                "map": "Baltic_Main",
                "duration_minutes": 28,
                "all_players_stats": {
                    player_name: {
                        "rank": 4,
                        "kills": 3,
                        "damage_dealt": 450.5,
                        "assists": 1,
                        "dbnos": 2,
                        "headshot_kills": 1,
                        "longest_kill": 187.3,
                        "revives": 1,
                        "revives_received": 0,
                        "heals_used": 3,
                        "boosts_used": 2,
                        "survival_time_minutes": 24.5,
                    }
                }
            }

            embed = create_enhanced_match_embed(fake_match, 1, 1)

            with open("test_embed.txt", "w", encoding="utf-8") as f:
                f.write(f"TITLE: {embed.title}\n")
                f.write(f"DESC:  {embed.description}\n\n")
                for field in embed.fields:
                    f.write(f"[{field.name}]\n{field.value}\n\n")

            await ctx.send(f"✅ Test embed for `{player_name}` saved to `test_embed.txt`")

        @self.client.command(name='weeklynow')
        async def weekly_now(ctx):
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("❌ Only administrators can do this!")
                return
            
            await ctx.send("📊 Generating weekly summary...")
            weekly_data = self.stats_manager.calculate_weekly_best(days=7)
            
            if not weekly_data:
                await ctx.send("⚠️ No data available for weekly stats!")
                return
            
            await ctx.send(f"✅ Data OK — {weekly_data['total_matches']} matches found")
            
            channel = self.client.get_channel(self.weekly_channel_id)
            if not channel:
                await ctx.send(f"❌ Channel not found! ID: `{self.weekly_channel_id}`")
                return
            
            await ctx.send(f"✅ Channel found: `{channel.name}`")
            
            try:
                best_embed = self.stats_manager.create_weekly_embed(weekly_data)
                await channel.send(embed=best_embed)
                await ctx.send("✅ Embed 1 sent!")
                await asyncio.sleep(2)
                leaderboard_embed = self.stats_manager.create_leaderboard_embed(weekly_data, top_n=5)
                await channel.send(embed=leaderboard_embed)
                await ctx.send("✅ Embed 2 sent!")
                await asyncio.sleep(2)
                alltime_embed = self.stats_manager.create_alltime_kills_embed()
                if alltime_embed:
                    await channel.send(embed=alltime_embed)
                    await ctx.send("✅ Done! All 3 embeds posted.")
                else:
                    await ctx.send("✅ Done! (2/3 embeds — run `scrape_longest_kills.py` to enable the all-time kills embed)")
            except Exception as e:
                await ctx.send(f"❌ Error: `{e}`")
        
    
    def save_players_to_file(self):
        """Save current player list to file — names only, no platform"""
        with open(self.players_file, 'w', encoding='utf-8') as f:
            f.write("# PUBG Players to Track\n")
            f.write("# Format: PlayerName  (one per line)\n")
            f.write("#\n")
            for name, _ in self.players:
                f.write(f"{name}\n")
    
    def load_posted_matches(self, filename: str = "posted_matches.json") -> Set[str]:
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"📋 Loaded {len(data)} previously posted matches")
                    return set(data)
            except Exception as e:
                logger.error(f"⚠️  Error loading posted matches: {e}")
                return set()
        return set()
    
    def save_posted_matches(self, filename: str = "posted_matches.json", max_history: int = 200):
        try:
            matches_list = list(self.posted_matches)[-max_history:]
            self.posted_matches = set(matches_list)
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(matches_list, f, indent=2)
            logger.info(f"💾 Saved {len(matches_list)} match IDs (max: {max_history})")
        except Exception as e:
            logger.error(f"⚠️  Error saving posted matches: {e}")
    
    async def on_ready(self):
        logger.info(f'✅ Bot connected as {self.client.user}')
        logger.info(f'📡 Tracking {len(self.players)} players')
        logger.info(f'📢 Posting to channel ID: {self.channel_id}')
        logger.info(f'🔄 Checking for new matches every {self.check_interval} seconds...')
        logger.info(f'💬 Commands: !addplayer <n>, !removeplayer <n>, !listplayers, !weeklynow\n')
        
        if not self.is_running:
            self.check_matches_loop.start()
            self.weekly_summary_loop.start()
            self.is_running = True
    
    @tasks.loop(seconds=1)
    async def check_matches_loop(self):
        try:
            logger.info(f"\n{'#'*80}")
            logger.info(f"# CYCLE {self.cycle_number} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'#'*80}\n")
            
            self.tracker.reset_cycle()
            
            tracked_player_names = [name for name, _ in self.players]
            
            for idx, (player_name, platform) in enumerate(self.players, 1):
                logger.info(f"{'─'*80}")
                logger.info(f"[{idx}/{len(self.players)}] Fetching: {player_name}")
                logger.info(f"{'─'*80}")
                
                await self.tracker.get_latest_match(player_name, platform, tracked_player_names)
                
                if idx < len(self.players):
                    logger.info(f"⏳ Waiting {self.tracker.request_delay}s before next player...")
                    await asyncio.sleep(self.tracker.request_delay)
                logger.info("")
            
            self.tracker.print_cycle_summary(self.cycle_number)
            
            if self.tracker.results:
                await self.post_matches_to_discord(self.tracker.results)
            
            self.cycle_number += 1
            
            logger.info(f"\n{'='*80}")
            logger.info(f"✅ Cycle {self.cycle_number - 1} complete! Next check in {self.check_interval}s...")
            logger.info(f"{'='*80}\n")
            
            await asyncio.sleep(self.check_interval)
            
        except Exception as e:
            logger.error(f"❌ Error in check loop: {e}")
            traceback.print_exc()
            await asyncio.sleep(60)
    
    @tasks.loop(hours=1)
    async def weekly_summary_loop(self):
        try:
            now = datetime.now(timezone.utc)
            
            if now.weekday() != 2 or now.hour != 18:
                return
            
            logger.info("\n" + "="*80)
            logger.info("📊 GENERATING WEEKLY SUMMARY - Wednesday 18:00 UTC")
            logger.info("="*80)
            
            weekly_data = self.stats_manager.calculate_weekly_best(days=7)
            
            if not weekly_data:
                logger.warning("⚠️ No data available for weekly summary")
                return
            
            channel = self.client.get_channel(self.weekly_channel_id)
            if not channel:
                logger.error(f"❌ Channel not found: {self.weekly_channel_id}")
                return
            
            best_embed = self.stats_manager.create_weekly_embed(weekly_data)
            await channel.send(embed=best_embed)
            logger.info("✅ Best player summary posted!")

            await asyncio.sleep(2)
            leaderboard_embed = self.stats_manager.create_leaderboard_embed(weekly_data, top_n=5)
            await channel.send(embed=leaderboard_embed)
            logger.info("✅ Leaderboard posted!")

            await asyncio.sleep(2)
            alltime_embed = self.stats_manager.create_alltime_kills_embed()
            if alltime_embed:
                await channel.send(embed=alltime_embed)
                logger.info("✅ All-time longest kills posted!")
            else:
                logger.warning("⚠️ No all-time kills data found — run scrape_longest_kills.py first")

            logger.info("="*80 + "\n")
            
        except Exception as e:
            logger.error(f"❌ Error posting weekly summary: {e}")
            traceback.print_exc()
    
    async def post_matches_to_discord(self, matches: List[dict]):
        try:
            channel = self.client.get_channel(self.channel_id)
            if not channel:
                logger.error(f"❌ Channel not found: {self.channel_id}")
                return
            
            new_matches = []
            
            for match in matches:
                match_id = match['match_id']
                if match_id not in self.posted_matches:
                    new_matches.append(match)
                    self.posted_matches.add(match_id)
                else:
                    logger.info(f"⏭️  Skipping already posted match: {match_id[:16]}...")
            
            if not new_matches:
                logger.info(f"📭 No new matches to post (all already posted)")
                return
            
            self.save_posted_matches()
            
            logger.info(f"\n📤 Posting {len(new_matches)} new matches to Discord...")
            
            for idx, match in enumerate(new_matches, 1):
                embed = create_enhanced_match_embed(match, idx, len(new_matches))
                if embed:
                    await channel.send(embed=embed)
                    players_in_match = list(match.get('all_players_stats', {}).keys())
                    logger.info(f"   ✅ Posted match {idx}/{len(new_matches)}: {', '.join(players_in_match)}")
                else:
                    logger.warning(f"   ⚠️  Skipped match {idx}/{len(new_matches)}: No player data")
                
                if idx < len(new_matches):
                    await asyncio.sleep(2)
            
            logger.info(f"   🎉 All {len(new_matches)} matches posted!")
            
            self.save_matches_for_stats(new_matches)
            
        except Exception as e:
            logger.error(f"❌ Error posting to Discord: {e}")
            traceback.print_exc()
    
    def save_matches_for_stats(self, matches: List[dict]):
        try:
            individual_matches = []
            
            for match in matches:
                all_players_stats = match.get('all_players_stats', {})
                
                for player_name, player_stats in all_players_stats.items():
                    individual_match = {
                        'player_name': player_name,
                        'match_id': match['match_id'],
                        'match_category': match['match_category'],
                        'game_mode': match['game_mode'],
                        'match_type': match['match_type'],
                        'is_custom': match['is_custom'],
                        'map': match['map'],
                        'duration_seconds': match['duration_seconds'],
                        'duration_minutes': match['duration_minutes'],
                        'played_at': match['played_at'],
                        'played_at_formatted': match['played_at_formatted'],
                        'player_stats': player_stats
                    }
                    individual_matches.append(individual_match)
            
            if individual_matches:
                self.stats_manager.save_match_history(individual_matches)
                logger.info(f"📊 Saved {len(individual_matches)} player records for weekly stats")
                
        except Exception as e:
            logger.error(f"⚠️ Error saving match history: {e}")
            traceback.print_exc()
    
    def run(self):
        try:
            self.client.run(self.discord_token)
        except Exception as e:
            logger.error(f"❌ Error starting bot: {e}")
            traceback.print_exc()
        finally:
            asyncio.run(self.tracker.close_session())
