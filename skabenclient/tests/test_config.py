import os
import time
import pytest
import multiprocessing as mp
import logging

from skabenclient.tests.conftest import _iface
from skabenclient.config import Config, SystemConfig, DeviceConfig

_sysconfig_dict = {
    "test": "test",
    "name": "main",
    "iface": _iface()
}

_devconfig_dict = {'device': 'testing',
                   'list_one': ['one', 'two', '3'],
                   'list_two': ['this', 'is', 'conf']}


def test_config_init(get_config):
    cfg = get_config(Config, {'test': 'main'})

    assert cfg.flock is not None, 'flock file was not created'


def test_config_update(get_config):
    cfg = get_config(Config, {'test': 'main'})
    update_from = {"name": "new_name"}
    cfg.update(update_from)

    assert cfg.data.get('name') == "new_name", "config was not updated"


def test_config_system_init(get_config):
    cfg = get_config(SystemConfig, _sysconfig_dict)
    test_keys = ['q_int', 'q_ext', 'ip', 'uid'] + list(_sysconfig_dict.keys())
    conf_keys = list(cfg.data.keys())
    test_keys.sort()
    conf_keys.sort()

    assert test_keys == conf_keys, 'bad config data'


def test_config_system_logger(get_config):
    cfg = get_config(SystemConfig, _sysconfig_dict)
    logger = cfg.logger()

    assert logger.level == logging.DEBUG, "bad logging level"
    assert len(logger.handlers) == 2, "bad number of logger handlers"


def test_config_device_init(get_config):
    cfg = get_config(DeviceConfig, _devconfig_dict)

    assert isinstance(cfg, DeviceConfig), 'wrong class'
    assert cfg.data == _devconfig_dict, 'bad config loaded'
