import os
import logging
import asyncio
from pathlib import Path

import discord
from discord.ext import commands
import dotenv

# Configure logging
def setup_logging():
    logs_dir = Path(__file__).parent.parent / 'logs'
    logs_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(logs_dir / 'devlin.log', encoding='utf-8', mode='a'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('devlin')


dotenv.load_dotenv()

logger = setup_logging()

class Devlin(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True

        super().__init__(
            intents=intents,
            activity=discord.Activity(type=discord.ActivityType.watching, name="over .gg/peretas"),
            command_prefix="#", #not used but yeah
            default_guild_ids=[1302533051405963264]
        )


        self.cogs_dir = Path(__file__).parent / 'cogs'

    def load_extensions(self):
        for cog_path in self.cogs_dir.glob('*.py'):
            if cog_path.stem != '__init__':
                try:
                    self.load_extension(f'src.cogs.{cog_path.stem}')
                    logger.info(f'Loaded cog: {cog_path.stem}')
                except Exception as e:
                    logger.error(f'Failed to load cog {cog_path.stem}: {e}')

    async def on_ready(self):
        await self.wait_until_ready()
        self.load_extensions()
        await self.sync_commands()
        logger.info(f'Logged in as {self.user.name} (ID: {self.user.id})')
        logger.info('Bot is ready and operational')



async def main():
    bot = Devlin()

    token = os.getenv('TOKEN')
    arcanetoken = os.getenv('ARCANE_TOKEN')
    if not token:
        logger.error('No Discord token found. Please check your .env file.')
        return

    try:
        await bot.start(token)
    except Exception as e:
        logger.error(f'An error occurred: {e}')
