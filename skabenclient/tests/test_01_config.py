import os
import time
import yaml
import pytest
import multiprocessing as mp
import logging

from skabenclient.config import Config, SystemConfig, DeviceConfig, FileLock
from skabenclient.loaders import get_yaml_loader

_devconfig = {'str': {'device': 'testing',
                      'list_one': ['one', 'two', {'3': 'number'}],
                      'list_two': [('this', 'is', 'not'), 'is', 'conf']},
              'int': {'device': 1,
                      'assume': [-2, 3.3, {'null': 0}]},
              'bool': {'device': True,
                       'blocked': False}
}

# TODO: config with empty device file


def test_config_init(get_config):
    """ Test initializes Config """
    cfg = get_config(Config, {'test': 'main'})

    assert isinstance(cfg, Config), 'bad instancing'


def test_config_write(get_config, default_config):
    """ Test write config to file """
    cfg = get_config(Config, default_config('sys'))

    try:
        cfg.write()
    except Exception as e:
        pytest.fail(f'exception raised as\n{e}')


def test_config_read(get_config):
    """ Test read config from file """
    test_dict = {'test': 'main'}
    cfg = get_config(Config, test_dict)

    cfg.write()
    read = cfg.read()
    assert isinstance(read, dict), f'read return wrong type: {type(read)}'
    assert read == test_dict, 'failed to read config'


def test_config_update(get_config):
    """ Test config update from dictionary """
    cfg = get_config(Config, {'test': 'main'})
    update_from = {"name": "new_name"}
    cfg.update(update_from)

    assert cfg.data.get('name') == "new_name", "config was not updated"


def test_config_create_file_empty(get_root, request):
    """ Test create new config file with empty content """
    path = os.path.join(get_root, 'res', 'non_existent.yml')
    cfg = Config(path)

    def config_td():
        try:
            os.remove(path)
            os.remove(f"{path}.lock")
        except FileNotFoundError:
            pass
        except Exception:
            raise

    request.addfinalizer(config_td)

    assert os.path.isfile(path), "config file not created"
    assert cfg.config_path == path, 'config path is incorrect'
    assert cfg.read() == dict(), 'empty config not loaded from file'


def test_config_create_file_with_default_dict(get_root, monkeypatch, request):
    """ Test create new config file with default parameters """
    path = os.path.join(get_root, 'res', 'non_existent.yml')
    default_conf = {'test': 'value'}
    monkeypatch.setattr(Config, 'default_config', default_conf)
    cfg = Config(path)
    with open(path, 'r') as fh:
        content = yaml.load(fh, Loader=get_yaml_loader())

    def config_td():
        try:
            os.remove(path)
            os.remove(f"{path}.lock")
        except FileNotFoundError:
            pass
        except Exception:
            raise

    request.addfinalizer(config_td)

    assert cfg.default_config == default_conf, "monkeypatch doesn't work"
    assert cfg.config_path == path, "config path is incorrect"
    assert content == default_conf, "config not written to file"
    assert cfg.data == default_conf, "default config not loaded from file"


def test_config_system_init(get_config, default_config):
    """ Test creates SystemConfig """
    config = default_config('sys')
    cfg = get_config(SystemConfig, config)
    test_keys = ['q_int', 'q_ext', 'ip', 'uid', 'device_conf'] + list(config.keys())
    conf_keys = list(cfg.data.keys())
    test_keys.sort()
    conf_keys.sort()

    assert test_keys == conf_keys, 'bad config data'


def test_config_system_logger(get_config, default_config):
    """ Test creates SystemConfig logger """
    cfg = get_config(SystemConfig, default_config('sys'))
    logger = cfg.logger()

    assert logger.level == logging.DEBUG, "bad logging level"
    assert len(logger.handlers) == 2, "bad number of logger handlers"


@pytest.mark.parametrize('config_dict', _devconfig.values())
def test_config_device_init(get_config, config_dict):
    """ Test creates DeviceConfig """
    cfg = get_config(DeviceConfig, config_dict)

    assert isinstance(cfg, DeviceConfig), 'wrong class'
    assert cfg.data == config_dict, 'bad config loaded'


def test_config_device_get_set(get_config):
    """ Test DeviceConfig get/set methods """
    test_dict = {'blocked': True}
    cfg = get_config(DeviceConfig, dict(**test_dict, **_devconfig.get('int')))

    get_data = cfg.get('blocked')
    cfg.set('blocked', False)

    assert get_data is True, 'bad getter'
    assert cfg.get('blocked') is False, 'bad setter'


@pytest.mark.parametrize('config_dict', _devconfig.values())
def test_config_device_save(get_config, config_dict):
    """ Test DeviceConfig save (update and write) """
    cfg = get_config(DeviceConfig, config_dict)
    cfg.save()
    with open(cfg.config_path, 'r') as fh:
        yml = yaml.load(fh.read(), Loader=get_yaml_loader())
    assert yml == config_dict, f'saved {yml} instead of {config_dict}'


@pytest.mark.parametrize('config_dict', _devconfig.values())
def test_config_device_load(get_config, config_dict):
    """ Test DeviceConfig load (read and update) """
    cfg = get_config(DeviceConfig, config_dict)
    cfg.save()
    cfg.data = dict()
    cfg.load()

    assert cfg.data == config_dict, 'data not loaded'


@pytest.mark.parametrize('config_dict', _devconfig.values())
def test_config_device_reset(get_config, config_dict):
    """ Test DeviceConfig reset to default parameters """
    cfg = get_config(DeviceConfig, config_dict)
    cfg.reset()
    cfg.save()
    new_conf = cfg.load()

    assert cfg.data == cfg.default_config, 'failed to apply default config'
    assert new_conf == cfg.default_config, 'failed to load default config'


def test_file_lock_context(get_config, monkeypatch):
    """ Test FileLock release """
    cfg = get_config(DeviceConfig, _devconfig.get('str'))
    file_lock = FileLock(cfg.config_path)
    # acquire lock context
    with file_lock:
        with open(file_lock.lock_path) as fh:
            content = fh.read().strip()
    # lock released, check lockfile content
    with open(file_lock.lock_path) as fh:
        no_lock_content = fh.read().strip()

    assert content == '1', 'value not written to lockfile'
    assert no_lock_content == '0', 'value not released'
    assert file_lock.locked is None, "not released"    
    assert file_lock.lock_path == f"{cfg.config_path}.lock"


def test_file_lock_busy(get_config, monkeypatch):
    """ Test FileLock when file locked """
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