import os
import time
import yaml
import pytest
import multiprocessing as mp
import logging

from skabenclient.tests.conftest import _iface
from skabenclient.config import Config, SystemConfig, DeviceConfig, FileLock
from skabenclient.loaders import get_yaml_loader

_sysconfig_dict = {
    "test": "test",
    "name": "main",
    "iface": _iface()
}

_devconfig = {'str': {'device': 'testing',
                      'list_one': ['one', 'two', {'3': 'number'}],
                      'list_two': [('this', 'is', 'not'), 'is', 'conf']},
              'int': {'device': 1,
                      'assume': [-2, 3.3, {'null': 0}]},
              'bool': {'device': True,
                       'blocked': False}
}


def test_config_init(get_config):
    cfg = get_config(Config, {'test': 'main'})

    assert isinstance(cfg, Config), 'bad instancing'


def test_config_write(get_config):
    cfg = get_config(Config, _sysconfig_dict)

    try:
        cfg.write()
    except Exception as e:
        pytest.fail(f'exception raised as\n{e}')


def test_config_read(get_config):
    test_dict = {'test': 'main'}
    cfg = get_config(Config, test_dict)

    cfg.write()
    read = cfg.read()
    assert isinstance(read, dict), f'read return wrong type: {type(read)}'
    assert read == test_dict, 'failed to read config'


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


@pytest.mark.parametrize('config_dict', _devconfig.values())
def test_config_device_init(get_config, config_dict):
    cfg = get_config(DeviceConfig, config_dict)

    assert isinstance(cfg, DeviceConfig), 'wrong class'
    assert cfg.data == config_dict, 'bad config loaded'


def test_config_device_get_set(get_config):
    test_dict = {'blocked': True}
    cfg = get_config(DeviceConfig, dict(**test_dict, **_devconfig.get('int')))

    get_data = cfg.get('blocked')
    cfg.set('blocked', False)

    assert get_data is True, 'bad getter'
    assert cfg.get('blocked') is False, 'bad setter'


@pytest.mark.parametrize('config_dict', _devconfig.values())
def test_config_device_save(get_config, config_dict):
    cfg = get_config(DeviceConfig, config_dict)
    cfg.save()
    with open(cfg.config_path, 'r') as fh:
        yml = yaml.load(fh.read(), Loader=get_yaml_loader())
    assert yml == config_dict, f'saved {yml} instead of {config_dict}'


@pytest.mark.parametrize('config_dict', _devconfig.values())
def test_config_device_load(get_config, config_dict):
    cfg = get_config(DeviceConfig, config_dict)
    cfg.save()
    cfg.data = dict()
    cfg.load()

    assert cfg.data == config_dict, 'data not loaded'


@pytest.mark.parametrize('config_dict', _devconfig.values())
def test_config_device_set_default(get_config, config_dict):
    cfg = get_config(DeviceConfig, config_dict)
    cfg.set_default()
    cfg.save()
    new_conf = cfg.load()

    assert cfg.data == cfg.default_config, 'failed to apply default config'
    assert new_conf == cfg.default_config, 'failed to load default config'


def test_file_lock_context(get_config, monkeypatch):
    cfg = get_config(DeviceConfig, _devconfig.get('str'))
    file_lock = FileLock(cfg.config_path)
    # acquire lock context
    with file_lock:
        with open(file_lock.lock_path) as fh:
            content = fh.read().strip()
    # lock released, check lockfile content
    with open(file_lock.lock_path) as fh:
        no_lock_content = fh.read().strip()

    assert content == '1', 'value not writed to lockfile'
    assert no_lock_content == '0', 'value not released'
    assert file_lock.locked is None, "not released"    
    assert file_lock.lock_path == f"{cfg.config_path}.lock"


def test_file_lock_busy(get_config, monkeypatch):
    cfg = get_config(DeviceConfig, _devconfig.get('str'))
    # just ignore time sleep
    monkeypatch.setattr(time, 'sleep', lambda x: None)
    file_lock = FileLock(cfg.config_path, timeout=.1)
    with file_lock:
        res = file_lock.acquire()
        with pytest.raises(Exception):
            assert cfg.write()
            assert cfg.read()

    assert res == None, 'lock acquired but should not'
