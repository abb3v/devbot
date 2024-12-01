import discord
from discord.ext import commands
from discord.commands import slash_command
import aiohttp
import asyncio
import json
import logging
import os
from dotenv import load_dotenv
import traceback
from datetime import datetime, timezone

# Load environment variables
load_dotenv()


class CleanupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Proper logger initialization
        self.logger = logging.getLogger('devlin.cogs.cleanup')

        # Ensure logger is configured
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)

        # Get the token from environment variables
        self.arcane_bot_token = os.getenv('ARCANE_BOT_AUTH_TOKEN')

        if not self.arcane_bot_token:
            self.logger.error("Arcane Bot Authorization Token not found in .env file!")

    async def fetch_leaderboard(self):
        """Fetch leaderboard and filter users based on specified conditions"""
        url = 'https://arcane.bot/api/guilds/1050867077742870558/levels/leaderboard'
        print(self.arcane_bot_token)
        headers = {
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://arcane.bot/leaderboard/thedevguild',
            'x-user-agent': 'Arcane-Bot-5.0',
            'Authorization': self.arcane_bot_token
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    self.logger.info(f"Leaderboard API Response Status: {response.status}")

                    if response.status == 200:
                        data = await response.json()
                        self.logger.debug(f"Leaderboard data received. Total users: {len(data.get('levels', []))}")
                        return data.get('levels', [])
                    else:
                        error_text = await response.text()
                        self.logger.error(
                            f"Leaderboard fetch failed. Status: {response.status}. Response: {error_text}")
                        return []
        except Exception as e:
            self.logger.error(f"Error fetching leaderboard: {e}")
            self.logger.error(traceback.format_exc())
            return []

    async def filter_users_to_kick(self, guild):
        """Filter users based on specified conditions"""
        self.logger.info("Starting user filtering process")

        leaderboard_users = await self.fetch_leaderboard()
        self.logger.info(f"Leaderboard users to process: {len(leaderboard_users)}")

        users_to_kick = []

        # Roles to exclude
        excluded_role_ids = {
            1071866368372244661,  # Boosters
            1050868103350861965,  # Real Ones (VIP)
            1311580509452898335,  # MODS
            1050867231761911889  # OWNERS
        }

        cutoff_date = datetime(2024, 11, 20, tzinfo=timezone.utc)

        for user_data in leaderboard_users:
            try:
                # Convert user ID to int
                user_id = int(user_data['id'])

                # Fetch the member
                try:
                    member = await guild.fetch_member(user_id)
                except discord.NotFound:
                    self.logger.info(f"User {user_id} not found in guild")
                    continue
                except discord.Forbidden:
                    self.logger.error(f"Cannot fetch member {user_id} due to permissions")
                    continue

                # Detailed logging for each member
                self.logger.debug(f"Processing member: {member.name} (ID: {member.id})")
                self.logger.debug(f"Member joined at: {member.joined_at}")
                self.logger.debug(f"Member bot status: {member.bot}")
                self.logger.debug(f"Member roles: {[role.id for role in member.roles]}")

                # Conditions for kicking
                conditions = [
                    user_data['level'] < 12,  # Level check
                    member.joined_at < cutoff_date,  # Join date check
                    not member.bot,  # Not a bot
                    not any(role.id in excluded_role_ids for role in member.roles)  # Not in excluded roles
                ]

                # If all conditions met, add to kick list
                if all(conditions):
                    users_to_kick.append({
                        'id': member.id,
                        'username': member.name,
                        'display_name': member.display_name
                    })
                    self.logger.info(f"Added {member.name} to kick list")

            except Exception as e:
                self.logger.error(f"Error processing user {user_data.get('id', 'Unknown')}: {e}")
                self.logger.error(traceback.format_exc())

        self.logger.info(f"Total users to kick: {len(users_to_kick)}")
        return users_to_kick

    @slash_command(name="cleanup", description="Cleanup guild members based on level and join date")
    @commands.has_permissions(administrator=True)
    async def cleanup_command(self, ctx: discord.ApplicationContext):
        """Main cleanup command with extensive error handling"""
        # Log command invocation
        self.logger.info(f"Cleanup command invoked by {ctx.author.name}")

        try:
            # Defer the response to prevent timeout
            await ctx.defer(ephemeral=True)

            # Find users to kick
            users_to_kick = await self.filter_users_to_kick(ctx.guild)

            # If no users to kick, inform and return
            if not users_to_kick:
                await ctx.followup.send("No users found matching kick criteria.", ephemeral=True)
                self.logger.info("No users found to kick")
                return

            # Create confirmation view
            class ConfirmView(discord.ui.View):
                def __init__(self, cog, ctx, users_to_kick):
                    super().__init__()
                    self.cog = cog
                    self.ctx = ctx
                    self.users_to_kick = users_to_kick

                @discord.ui.button(label="Confirm Cleanup", style=discord.ButtonStyle.danger)
                async def confirm_button(self, button: discord.ui.Button, interaction: discord.Interaction):
                    kick_count = 0
                    error_count = 0
                    detailed_errors = []

                    for user_info in self.users_to_kick:
                        try:
                            member = self.ctx.guild.get_member(user_info['id'])
                            if member:
                                # DM the user before kicking
                                try:
                                    await member.send(
                                        "Dev Guild | You have been kicked. Unfortunately, you did not reach the level requirement to be a member. You may reapply at https://discord.gg/devguild")
                                except Exception as dm_error:
                                    self.cog.logger.warning(
                                        f"Could not DM {user_info['username']} before kick: {dm_error}")

                                # Kick the member
                                await member.kick(reason="Did not meet level requirements")
                                kick_count += 1
                                self.cog.logger.info(f"Kicked {user_info['username']}")
                        except Exception as e:
                            error_count += 1
                            detailed_errors.append(f"{user_info['username']}: {str(e)}")
                            self.cog.logger.error(f"Error kicking {user_info['username']}: {e}")

                    # Construct result message
                    result_message = f"✅ Cleanup completed.\n"
                    result_message += f"Kicked: {kick_count} members\n"
                    if error_count > 0:
                        result_message += f"Errors: {error_count}\n"
                        if detailed_errors:
                            result_message += "Error details:\n" + "\n".join(detailed_errors[:5])

                    await interaction.response.edit_message(content=result_message, view=None)

                @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
                async def cancel_button(self, button: discord.ui.Button, interaction: discord.Interaction):
                    await interaction.response.edit_message(content="Cleanup cancelled.", view=None)

            # Create an embed with user information
            embed = discord.Embed(
                title="Member Cleanup Confirmation",
                description=f"Found {len(users_to_kick)} members to kick",
                color=discord.Color.red()
            )

            # Add details to embed
            if users_to_kick:
                # Limit to first 10 users in the embed
                user_list = "\n".join([f"{u['display_name']} (ID: {u['id']})" for u in users_to_kick[:10]])
                embed.add_field(name="Sample Users", value=user_list, inline=False)
                if len(users_to_kick) > 10:
                    embed.set_footer(text=f"... and {len(users_to_kick) - 10} more")

            # Send confirmation message with view
            await ctx.followup.send(
                embed=embed,
                view=ConfirmView(self, ctx, users_to_kick),
                ephemeral=True
            )

        except Exception as e:
            self.logger.error(f"Critical error in cleanup command: {e}")
            self.logger.error(traceback.format_exc())
            await ctx.followup.send(f"An unexpected error occurred: {str(e)}", ephemeral=True)


def setup(bot):
    bot.add_cog(CleanupCog(bot))