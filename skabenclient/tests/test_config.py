import os
import pytest
import multiprocessing as mp
import logging

from skabenclient.helpers import get_mac, get_ip
from skabenclient.config import Config

config_dict = {
    "cfig": "test",
    "name": "main"
}


def test_config_create(write_config):
    path = write_config(config_dict)
    config = Config(path)

    assert isinstance(config, Config), "cannot load config"
    for q in (config.q_ext, config.q_int):
        assert isinstance(q, mp.queues.Queue), "not a queue"


def test_config_logger(write_config):
    path = write_config(config_dict)
    config = Config(path)
    logger = config.logger()
    
    assert logger.level == logging.DEBUG, "bad logging level"
    assert len(logger.handlers) == 2, "bad number of logger handlers"


def test_config_update(write_config):
    path = write_config(config_dict)
    config = Config(path)

    update_from = {"name": "new_name"}
    config.update(update_from)

    assert config.name == "new_name", "config was not updated"
