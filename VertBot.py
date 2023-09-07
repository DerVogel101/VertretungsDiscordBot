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
from pprint import pprint

sys.path.insert(1, "./lib")
from file_man import load_json_dict, save_json_dict


def signal_handler(sig, frame):
    """Close client and exit program"""
    print("Beende Programm...")
    asyncio.create_task(client.close())
    sys.exit(0)


if __name__ == "__main__":
    # Load .env
    load_dotenv()

    # Intents
    intents = discord.Intents.all()
    intents.members = True

    # Client and Command Tree
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    # Discord Server List
    discord_server_list: list = eval(os.getenv("SERVERIDLIST"))
    for i, discord_server in enumerate(discord_server_list):
        discord_server_list[i] = discord.Object(id=discord_server)

    # Create empty data.json if not exists
    try:
        with open("data.json", "x") as _:
            pass
    except FileExistsError:
        pass

    # Default structure for data.json
    # Structure:
    # {"servers": {
    #     server_id: {  # e.g. 123456789 type: int
    #         "subjects": {
    #             {subject_name: {  # e.g. "Mathe" type: str
    #                 "teacher": str,  # teacher name
    #                 "abscences": {
    #                     {date: {  # e.g. "2021-09-01" type: str
    #                         "reason": str,  # reason for abscence (e.g. "Krank")
    #                         "is_late": bool,  # if the teacher is late
    #                         "length": int,  # in minutes if is_late is True else in hours
    #                         "is_replaced": bool,  # if a replacement teacher is set
    #                         "replacement_present": bool,  # if the replacement teacher is present  or on "mit betreuung"
    #                         "period": list[int, int],  # [start, end] in format [start period, end period]
    #                         "note": str,  # optional note
    #                         "reporter_id": int  # discord id of the reporter
    #                     }}
    #                 }
    #             }}
    #         },
    #         "channel": int,  # channel id of the channel where the bot should send and recive the messages
    #         "reporter_role": int  # role id of the reporter role
    #     }
    # }}




    default_database_structure = [
        ("servers", {}),
    ]

    # Function to load a json file or write an empty {} to it if its empty using a json.dump
    database = load_json_dict("data.json", default_database_structure)

    # Function to save the database variable to data.json
    def save_database() -> None:
        """Saves the database variable to data.json"""
        save_json_dict("data.json", database)


    def register_servers_database() -> None:  # Function to register a server in the database
        """Registers all servers in the database"""
        for guild in client.guilds:
            if str(guild.id) not in database:
                database[str(guild.id)] = {}
                save_database()
                print(f"Registered {guild.name} in database")


    # Crash handling
    signal.signal(signal.SIGINT, signal_handler)

    # start Bot
    client.run(os.getenv("TOKEN"))
