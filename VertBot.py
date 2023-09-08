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
from copy import deepcopy

sys.path.insert(1, "./lib")  # Add lib folder to path



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
    NOTUSED = {"servers": {
        server_id: {  # e.g. 123456789 type: int
            "absences": {
                {date: {  # e.g. "2021-09-01" type: str
                    {subject_name: {  # e.g. "Mathe" type: str
                        "teacher": str,  # teacher name
                        "reason": str,  # reason for abscence (e.g. "Krank")
                        "is_late": bool,  # if the teacher is late
                        "length": int,  # in minutes if is_late is True
                        "is_replaced": bool,  # if a replacement teacher is set
                        "replacement_present": bool,  # if the replacement teacher is present  or on "mit betreuung"
                        "period": list[int, int],  # [start, end] in format [start period, end period]
                        "note": str,  # optional note
                        "reporter_id": int  # discord id of the reporter
                    }}

                }}
            },
            "channel": int,  # channel id of the channel where the bot should send and recive the messages
            "reporter_role": int  # role id of the reporter role
        }
    }}


    class DiscordDatabaseApi:
        class InvalidFileError(Exception):
            pass

        def __init__(self, file_name: str) -> None:
            self.__file_name = file_name
            self.__load()  # Load database from file into self.__database

        def __genrate_empty(self) -> None:
            try:
                with open(self.__file_name, "x") as f:
                    json.dump({"servers": {}}, f)
            except FileExistsError:
                pass

        def __load(self) -> None:
            for _ in range(2):
                try:
                    with open(self.__file_name, "r") as file:
                        self.__database = json.load(file)
                    break
                except FileNotFoundError:
                    self.__genrate_empty()
                except json.decoder.JSONDecodeError:
                    raise self.InvalidFileError("The file is not a valid json file")
            else:
                raise self.InvalidFileError("The file could not be generated")

        def __save(self) -> None:
            with open(self.__file_name, "w") as file:
                json.dump(self.__database, file)

        def print(self) -> None:  # FIXME: Only for testing
            pprint(self.__database)

        def get_database(self) -> dict:  # FIXME: Only for testing
            self.__load()
            return deepcopy(self.__database)

        def register_servers(self, register_client: discord.client.Client) -> None:
            """Registers all servers in the database"""
            for guild in register_client.guilds:
                if str(guild.id) not in self.__database["servers"]:
                    self.__database["servers"][str(guild.id)] = {"absences": {}, "channel": None, "reporter_role": None}
                    self.__save()
                    print(f"Registered {guild.name} in database")

        # TODO: set_channel, set_subjects, set_channel, set_reporter_role, get_subjects, get_channel, get_reporter_role
        ...

    test = DiscordDatabaseApi("data.json")

    # Crash handling
    signal.signal(signal.SIGINT, signal_handler)

    # start Bot
    client.run(os.getenv("TOKEN"))
