import os
import time
import yaml
import pytest
import logging

from skabenclient.config import Config, SystemConfig, DeviceConfig, FileLock, loggers
from skabenclient.loaders import get_yaml_loader

_devconfig = {'str': {'device': 'testing',
                      'list_one': ['one', 'two', {'3': 'number'}],
                      'list_two': [('this', 'is', 'not'), 'is', 'conf']},
              'int': {'device': 1,
                      'assume': [-2, 3.3, {'null': 0}]},
              'bool': {'device': True,
                       'blocked': False}
}


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


@pytest.mark.parametrize('conf_obj', (Config, SystemConfig))
def test_config_file_empty(get_empty_config, monkeypatch, get_root, conf_obj):
    """ Test config write default """
    path = os.path.join(get_root, 'res', 'missing.yml')

    with pytest.raises(FileNotFoundError):
        get_empty_config(conf_obj, path)


def test_config_create_file_with_default_dict(get_root, get_empty_config, monkeypatch):
    """ Test create new config file with default parameters """
    path = os.path.join(get_root, 'res', 'non_existent.yml')
    test_dict = {'this': 'test', 'test': 'de'}
    monkeypatch.setattr(DeviceConfig, 'minimal_essential_conf', test_dict)
    cfg = get_empty_config(DeviceConfig, path)

    with open(path, 'r') as fh:
        content = yaml.load(fh, Loader=get_yaml_loader())

    assert cfg.config_path == path, "config path is incorrect"
    assert cfg.minimal_essential_conf == test_dict, "bad minimal running"
    assert content == test_dict, "config not written to file"
    assert cfg.data == test_dict, "default config not loaded from file"


def test_config_system_init_base(get_config, default_config):
    """ Test creates SystemConfig """
    config = default_config('sys')
    cfg = get_config(SystemConfig, config)
    test_keys = ['q_int', 'q_ext', 'ip', 'uid', 'listen', 'publish'] \
                + list(config.keys())
    conf_keys = list(cfg.data.keys())
    test_keys.sort()
    conf_keys.sort()

    assert conf_keys == test_keys, 'inconsistent config keys'


def test_config_system_logger(get_config, default_config):
    """ Test creates SystemConfig logger """
    cfg = get_config(SystemConfig, default_config('sys'))
    logger = cfg.logger()

    assert logger.level == logging.DEBUG, "bad logging level"
    assert len(logger.handlers) == 2, "bad number of logger handlers"
    assert loggers.get('main') is logger


@pytest.mark.skip(reason='no custom logging yet')
def test_config_system_logger_fpath(get_config, default_config):
    """ Test creates SystemConfig logger """
    cfg = get_config(SystemConfig, default_config('sys'))
    real_root = os.path.abspath(os.path.dirname(__file__))
    file_path = os.path.join(real_root, 'res', 'logtest.log')

    logger = cfg.logger(file_path=file_path,
                        log_level=logging.ERROR)

    #assert logger.level == logging.ERROR, "bad logging level"
    for handler in logger.handlers:
        fname = getattr(handler, 'baseFilename')
        if fname:
            assert fname == file_path, 'wrong file path passed to logger handler'


def test_config_device_init(get_config, monkeypatch):
    """ Test creates DeviceConfig """
    # WARN: this monkeypatching hardcoded on _devconfig keys
    # setattr for passing DeviceConfig.read() consistency check
    monkeypatch.setattr(DeviceConfig, 'minimal_essential_conf', {'int': 1})
    cfg = get_config(DeviceConfig, _devconfig)

    assert isinstance(cfg, DeviceConfig), 'wrong class'
    assert cfg.data == _devconfig, 'bad config loaded'


def test_config_device_init_with_defaults(get_config, monkeypatch):
    """ Test creates DeviceConfig with minimal essential conf """
    # WARN: this monkeypatching hardcoded on _devconfig keys
    # setattr for passing DeviceConfig.read() consistency check
    not_devconfig = {'not_presented': 1}
    monkeypatch.setattr(DeviceConfig, 'minimal_essential_conf', not_devconfig)
    cfg = get_config(DeviceConfig, _devconfig)

    assert isinstance(cfg, DeviceConfig), 'wrong class'
    assert cfg.data == not_devconfig, 'bad config loaded'


@pytest.mark.parametrize('config_dict', (_devconfig,))
def test_config_device_save(get_config, config_dict):
    """ Test DeviceConfig save (update and write) """
    cfg = get_config(DeviceConfig, config_dict)
    cfg.save()
    with open(cfg.config_path, 'r') as fh:
        yml = yaml.load(fh.read(), Loader=get_yaml_loader())
    assert yml == config_dict, f'saved {yml} instead of {config_dict}'


def test_config_device_get_set(get_config):
    """ Test DeviceConfig get/set methods """
    test_dict = {'blocked': True}
    cfg = get_config(DeviceConfig, dict(**test_dict, **_devconfig.get('int')))

    get_data = cfg.get('blocked')
    cfg.set('blocked', False)

    assert get_data is True, 'bad getter'
    assert cfg.get('blocked') is False, 'bad setter'


@pytest.mark.parametrize('config_dict', (_devconfig,))
def test_config_device_load(get_config, config_dict):
    """ Test DeviceConfig load (read and update) """
    cfg = get_config(DeviceConfig, config_dict)
    cfg.save()
    cfg.data = dict()
    cfg.load()

    assert cfg.data == config_dict, 'data not loaded'


def test_config_device_reset(get_config, monkeypatch):
    """ Test DeviceConfig reset to default parameters """
    monkeypatch.setattr(DeviceConfig, 'minimal_essential_conf', {'test': 'conf'})
    cfg = get_config(DeviceConfig, _devconfig)
    cfg.save()
    cfg.write_default()
    new_conf = cfg.load()

    assert cfg.data == cfg.minimal_essential_conf, 'failed to apply default config'
    assert new_conf == cfg.minimal_essential_conf, 'failed to load default config'


def test_config_device_restore_empty(get_config, write_config_fixture, monkeypatch):
    """ Test DeviceConfig restore when file is corrupted """
    fname = 'will_be_empty.yml'
    # saving normal conf
    is_default = {'test': 'conf'}
    monkeypatch.setattr(DeviceConfig, 'minimal_essential_conf', is_default)
    cfg = get_config(DeviceConfig, _devconfig, fname=fname)
    cfg.save()
    write_config_fixture('', fname)
    should_be_default = cfg.read()

    assert should_be_default == is_default, 'configs not matched'


def test_config_device_restore_broken(get_config, write_config_fixture, monkeypatch):
    """ Test DeviceConfig restore when file is corrupted """
    fname = 'will_be_broken.yml'
    # saving normal conf
    is_default = {'test': 'conf'}
    monkeypatch.setattr(DeviceConfig, 'minimal_essential_conf', is_default)
    cfg = get_config(DeviceConfig, _devconfig, fname=fname)
    cfg.save()
    write_config_fixture('<< EOF >>', fname)
    should_be_default = cfg.read()

    assert should_be_default == is_default, 'configs not matched'

@pytest.mark.parametrize('config_dict', (_devconfig,))
def test_config_device_restore_missing(get_config, config_dict, monkeypatch, write_config_fixture):
    """ Test DeviceConfig restore when file is corrupted """
    fname = 'will_be_missing.yml'
    # saving normal conf
    is_default = {'test': 'conf'}
    monkeypatch.setattr(DeviceConfig, 'minimal_essential_conf', is_default)
    cfg = get_config(DeviceConfig, config_dict, fname=fname)
    cfg.save()
    path = write_config_fixture('corrupted_string', fname)
    os.remove(path)
    # trying to read from non-existent file
    should_be_default = cfg.read()

    assert should_be_default == is_default, 'configs not matched'


@pytest.mark.parametrize('config_dict', (_devconfig,))
def test_file_lock_context(get_config, config_dict):
    """ Test FileLock release """
    cfg = get_config(DeviceConfig, config_dict.get('str'))
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


@pytest.mark.parametrize('config_dict', (_devconfig,))
def test_file_lock_busy(get_config, monkeypatch, config_dict):
    """ Test FileLock when file locked """
    cfg = get_config(DeviceConfig, config_dict.get('str'))
    # just ignore time sleep
    monkeypatch.setattr(time, 'sleep', lambda x: None)
    file_lock = FileLock(cfg.config_path, timeout=.1)
    with file_lock:
        res = file_lock.acquire()
        with pytest.raises(Exception):
            assert cfg.write()
            assert cfg.read()

    assert res == None, 'lock acquired but should not'
