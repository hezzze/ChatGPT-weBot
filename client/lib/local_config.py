import os.path as osp
from os import getenv
import json


def configure():
    """
    Looks for a config file in the following locations:
    """
    config_files = [".config/local_config.json"]

    if config_file := next((f for f in config_files if osp.exists(f)), None):
        with open(config_file, encoding="utf-8") as f:
            config = json.load(f)
    else:
        print("No config file found.")
        raise Exception("No config file found.")
    return config


local_config = configure()
