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
            "subjects": dict[str:str],  # dict of subjects with the subject name as key and the teacher name as value
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
                                                                 "subjects": {}}
                    self._save()
                    print(f"Registered {guild.name} in database")

        def set_subjects(self, server_id: str, subjects: dict[str:str], mode: str) -> None:
            """Sets the subjects for a server
            :param server_id: id of the server
            :param subjects: dict of subjects with the subject name as key and the teacher name as value
            :param mode: "a" or "s" for add or set
            """
            match mode:
                case "a":
                    self._database["servers"][server_id]["subjects"].update(subjects)
                case "s":
                    self._database["servers"][server_id]["subjects"]: dict[str:str] = subjects
                case _:
                    raise ValueError("mode must be 'a' or 's'")
            self._save()

        def get_subjects(self, server_id: str) -> dict[str:str]:
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

            def set_teacher(self, teacher: str = None) -> None:
                """Sets the teacher name"""
                if teacher is None:
                    teacher = self.__database.get_subjects(self.__server_id)[self.__subject_name]
                elif teacher not in self.__database.get_subjects(self.__server_id).values():
                    teacher = "Unbekannt"
                self.__absence_data["teacher"] = teacher

            def get_teacher(self) -> str:
                """Returns the teacher name"""
                return self.__absence_data["teacher"]

            def set_reason(self, reason: str = None) -> None:
                """Sets the reason for absence"""
                if reason is None:
                    reason = "Unbekannt"
                self.__absence_data["reason"] = reason

            def get_reason(self) -> str:
                """Returns the reason for absence"""
                return self.__absence_data["reason"]

            def set_is_late(self, is_late: bool = False) -> None:
                """Sets if the teacher is late"""
                self.__absence_data["is_late"] = is_late

            def get_is_late(self) -> bool:
                """Returns if the teacher is late"""
                return self.__absence_data["is_late"]

            def set_length(self, length: int = None) -> None:
                """Sets the length of the absence"""
                if length is None:
                    length = 0
                self.__absence_data["length"] = length

            def get_length(self) -> int:
                """Returns the length of the absence"""
                return self.__absence_data["length"]

            def set_is_replaced(self, is_replaced: bool = False) -> None:
                """Sets if the teacher is replaced"""
                self.__absence_data["is_replaced"] = is_replaced

            def get_is_replaced(self) -> bool:
                """Returns if the teacher is replaced"""
                return self.__absence_data["is_replaced"]

            def set_replacement_present(self, replacement_present: bool = False) -> None:
                """Sets if the replacement teacher is present"""
                self.__absence_data["replacement_present"] = replacement_present

            def get_replacement_present(self) -> bool:
                """Returns if the replacement teacher is present"""
                return self.__absence_data["replacement_present"]

            def set_period(self, period: list[int, int] = None) -> None:
                """Sets the period of the absence"""
                if period is None:
                    period = [0, 0]
                self.__absence_data["period"] = period

            def get_period(self) -> list[int, int]:
                """Returns the period of the absence"""
                return self.__absence_data["period"].copy()

            def set_note(self, note: str = None) -> None:
                """Sets the note of the absence"""
                if note is None:
                    note = ""
                self.__absence_data["note"] = note

            def get_note(self) -> str:
                """Returns the note of the absence"""
                return self.__absence_data["note"]

            def set_reporter_id(self, reporter_id: int = None) -> None:
                """Sets the reporter id"""
                if reporter_id is None:
                    reporter_id = 0
                self.__absence_data["reporter_id"] = reporter_id

            def get_reporter_id(self) -> int:
                """Returns the reporter id"""
                return self.__absence_data["reporter_id"]

            def get_absence_data(self) -> dict:
                """Returns the absence data"""
                return deepcopy(self.__absence_data)

            def write_save(self) -> None:
                """Writes the data to the database"""
                self.__data["servers"][self.__server_id]["absences"][self.__date][self.__subject_name].append(
                    self.__absence_data)
                self.__database._save()


    test = DiscordDatabaseApi("data.json")

    # Crash handling
    signal.signal(signal.SIGINT, signal_handler)

    # start Bot
    client.run(os.getenv("TOKEN"))
