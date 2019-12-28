import os
import pytest
import sqlite3
import skabenclient.managers as mgr
from skabenclient.config import SystemConfig
from skabenclient.tests.mock import schemas


def test_base_manager(get_config):
    config = get_config(SystemConfig, {'dev_type': 'test', "iface": "eth0"})
    base = mgr.BaseManager(config)

    assert base.config == config.data, 'wrong config load'
    assert base.reply_channel == 'test' + 'ask'
