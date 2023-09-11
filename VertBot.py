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
        server_id: {  # e.g. 123456789 type: str
            "subjects": list[str],  # list of all subjects
            "channel": int,  # channel id of the channel where the bot should send and recive the messages
            "reporter_role": int,  # role id of the reporter role
            "absences": {
                date: {  # %d.%m.%Y type: str
                    subject_name: [{  # e.g. "Mathe" type: str
                        "teacher": str,  # teacher name
                        "reason": str,  # reason for abscence (e.g. "Krank")
                        "is_late": bool,  # if the teacher is late
                        "length": int,  # in minutes if is_late is True
                        "is_replaced": bool,  # if a replacement teacher is set
                        "replacement_present": bool,  # if the replacement teacher is present  or on "mit betreuung"
                        "period": list[int, int],  # [start, end] in format [start period, end period]
                        "note": str,  # optional note
                        "reporter_id": int  # discord id of the reporter
                    }]}
                }
            }
        }
    }


    class DiscordDatabaseApi:
        class InvalidFileError(Exception):
            pass

        def __init__(self, file_name: str) -> None:
            self.__file_name = file_name
            self._load()  # Load database from file into self._database

        def __genrate_empty(self) -> None:
            try:
                with open(self.__file_name, "x") as f:
                    json.dump({"servers": {}}, f)
            except FileExistsError:
                pass

        def _load(self) -> None:
            for _ in range(2):
                try:
                    with open(self.__file_name, "r") as file:
                        self._database = json.load(file)
                    break
                except FileNotFoundError:
                    self.__genrate_empty()
                except json.decoder.JSONDecodeError:
                    raise self.InvalidFileError("The file is not a valid json file")
            else:
                raise self.InvalidFileError("The file could not be generated")

        def _save(self) -> None:
            with open(self.__file_name, "w") as file:
                json.dump(self._database, file)

        def print(self) -> None:  # FIXME: Only for testing
            pprint(self._database)

        def get_database(self) -> dict:  # FIXME: Only for testing
            self._load()
            return deepcopy(self._database)

        def register_servers(self, register_client: discord.client.Client) -> None:
            """Registers all servers in the database"""
            for guild in register_client.guilds:
                if str(guild.id) not in self._database["servers"]:
                    self._database["servers"][str(guild.id)] = {"absences": {}, "channel": None, "reporter_role": None,
                                                                 "subjects": []}
                    self._save()
                    print(f"Registered {guild.name} in database")

        def set_subjects(self, server_id: str, subjects: list[str], mode: str) -> None:
            """Sets the subjects for a server
            :param server_id: id of the server
            :param subjects: list of subjects
            :param mode: "a" or "s" for add or set
            """
            match mode:
                case "a":
                    self._database["servers"][server_id]["subjects"].extend(subjects)
                case "s":
                    self._database["servers"][server_id]["subjects"] = subjects
                case _:
                    raise ValueError("mode must be 'a' or 's'")
            self._save()

        def get_subjects(self, server_id: str) -> list[str]:
            """Returns all subjects"""
            return deepcopy(self._database["servers"][server_id]["subjects"])

        def set_channel(self, server_id: str, channel_id: int) -> None:
            """Sets the channel where the bot should send and recive messages"""
            self._database["servers"][server_id]["channel"] = channel_id
            self._save()

        def get_channel(self, server_id: str) -> int:
            """Returns the channel id"""
            return self._database["servers"][server_id]["channel"]

        def set_reporter_role(self, server_id: str, role_id: int) -> None:
            """Sets the role which can report absences"""
            self._database["servers"][server_id]["reporter_role"] = role_id
            self._save()

        def get_reporter_role(self, server_id: str) -> int:
            """Returns the role id"""
            return self._database["servers"][server_id]["reporter_role"]

        class Absence:
            @staticmethod
            def validate_date(date_string, date_format):
                try:
                    datetime.strptime(date_string, date_format)
                    return True
                except ValueError:
                    return False

            def __init__(self, database: "DiscordDatabaseApi", server_id: str, date: str, subject_name: str) -> None:
                """Absence class
                Should not be used in some sort of multi-threading environment, because it does not save to the database
                if the method for the save is not called, could end up in database corruption
                :param database: DiscordDatabaseApi
                :param server_id: id of the server
                :param date: date in format %d.%m.%Y
                :param subject_name: name of the subject
                """
                self.__data = database._database  # database dict from DiscordDatabaseApi
                self.__database = database  # database class from DiscordDatabaseApi

                if server_id not in self.__data["servers"]:
                    raise ValueError(f"Server {server_id} not in database")
                if subject_name not in self.__database.get_subjects(server_id):
                    raise ValueError(f"Subject {subject_name} not in subjects")
                if not self.validate_date(date, "%d.%m.%Y"):
                    raise ValueError(f"Date {date} not in format %d.%m.%Y")

                self.__server_id = server_id
                self.__date = date
                self.__subject_name = subject_name
                self.__absence_data = {}

                if date not in self.__data["servers"][self.__server_id]["absences"]:
                    self.__data["servers"][self.__server_id]["absences"][self.__date] = {}
                if self.__subject_name not in self.__data["servers"][self.__server_id]["absences"][self.__date]:
                    self.__data["servers"][self.__server_id]["absences"][self.__date][self.__subject_name] = []


            # TODO: Add __absence_data editing methods, __absence_data getter and save method


    test = DiscordDatabaseApi("data.json")

    # Crash handling
    signal.signal(signal.SIGINT, signal_handler)

    # start Bot
    client.run(os.getenv("TOKEN"))
