from dotenv import load_dotenv
from discord import app_commands
from discord.ext import tasks
import discord
import json
from datetime import datetime
import asyncio
import signal
import sys
import os


def signal_handler(sig, frame):
    """Close client and exit program"""
    print("Beende Programm...")
    asyncio.create_task(client.close())
    sys.exit(0)


if __name__ == "__main__":
    # Intents
    intents = discord.Intents.all()
    intents.members = True

    # Client and Command Tree
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    # Discord Server List
    discord_server_list: list = [1040706320384409752, 1015266925493891082]
    for discord_server in range(len(discord_server_list)):
        discord_server_list[discord_server]: list = discord.Object(id=discord_server_list[discord_server])

    # Create empty data.json if not exists
    try:
        with open('data.json', 'x') as _:
            pass
    except FileExistsError:
        pass

    # Function to load a json file or write an empty {} to it if its empty using a json.dump
    def load_json(file: str):
        with open(file, 'r+') as f:
            try:
                return json.load(f)
            except json.decoder.JSONDecodeError:
                json.dump({}, f)
                return {}


    # Crash handling
    signal.signal(signal.SIGINT, signal_handler)

    # Load .env
    load_dotenv()
    # start Bot
    client.run(os.getenv('TOKEN'))
