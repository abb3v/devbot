import discord
from discord.commands import slash_command  # Add this import
from discord.ext import commands
import logging

logger = logging.getLogger('devlin.cogs.ping')


class PingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info('Ping cog initialized')

    @slash_command(name="ping", description="Check bot's latency")
    async def ping(self, ctx: discord.ApplicationContext):
        try:
            latency = round(self.bot.latency * 1000, 2)
            await ctx.respond(f'🏓 Pong! Latency: {latency}ms')
            logger.info(f'Ping command used. Latency: {latency}ms')
        except Exception as e:
            logger.error(f'Error in ping command: {e}')
            await ctx.respond('❌ An error occurred while checking latency.')

def setup(bot):
    bot.add_cog(PingCog(bot))
