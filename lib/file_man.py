import json
from copy import deepcopy


def load_json_dict(file: str, default_structure: list[tuple]) -> dict:
    """
    Loads a json file to a dict. If the file is empty, it will be filled with the default_structure.
    :param file: The file to load
    :param default_structure: The default structure to fill the file with if it is empty (e.g. [("key", "value")]
    :return: The dict
    """
    with open(file, 'r+') as f:
        try:
            return json.load(f)
        except json.decoder.JSONDecodeError:
            default_structure_dict = {}
            for key, value in deepcopy(default_structure):
                default_structure_dict[key] = value
            json.dump(default_structure_dict, f)
            return default_structure_dict


def save_json_dict(file: str, dict_to_save: dict):
    """
    Saves a dict to a json file.
    :param file: The file to save
    :param dict_to_save: The dict to save
    """
    with open(file, 'w') as f:
        json.dump(dict_to_save, f)
