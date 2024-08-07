import logging
import os
import time

import pytest
import yaml

from skabenclient.config import Config, DeviceConfig, FileLock, SystemConfig
from skabenclient.helpers import Event
from skabenclient.loaders import get_yaml_loader
from skabenclient.tests.mock.data import base_config, yaml_content, yaml_content_as_dict


@pytest.fixture(autouse=True)
def cleanup_logger_handlers():
    yield
    loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    loggers.append(logging.getLogger())  # add root logger to list
    [logger.handlers.clear() for logger in loggers]


def test_config_init(get_config):
    """ Test initializes Config """
    cfg = get_config(Config, {'test': 'main'})

    assert isinstance(cfg, Config), 'failed to init config'


def test_config_yaml_loads(get_config, write_config_fixture):
    """ Test read config from file """
    cfg = get_config(Config, {"test": "test"})
    readed = cfg._yaml_load(yaml_content)
    assert readed == yaml_content_as_dict


def test_config_yaml_dumps(get_config, write_config_fixture):
    """ Test read config from file """
    cfg = get_config(Config, yaml_content_as_dict)
    cfg.write()

    with open(cfg.config_path, 'r') as fh:
        writed_content = fh.read()

    writed = cfg._yaml_load(writed_content)
    pure = cfg._yaml_load(yaml_content)
    assert writed == pure, f"DID NOT MATCHED:\n{writed}{'-'*80}{pure}"


def test_config_write(get_config, default_config):
    """ Test write config to file """
    cfg = get_config(Config, default_config('sys'))

    try:
        cfg.write()
    except Exception as e:
        pytest.fail(f'exception raised as\n{e}')


def test_config_read(get_config, write_config_fixture):
    """ Test read config from file """
    test_dict = {'test': 'main'}
    cfg = get_config(Config, test_dict)
    write_config_fixture(test_dict, cfg.config_path)

    read = cfg.read()
    assert isinstance(read, dict), f'read return wrong type: {type(read)}'
    assert read == test_dict, 'failed to read config'


def test_config_update(get_config):
    """ Test config update from dictionary """
    cfg = get_config(Config, {'test': 'main'})
    update_from = {"name": "new_name"}
    cfg.update(update_from)

    assert cfg.data.get('name') == "new_name", "config was not updated"


def test_config_update_nested(get_config):
    val = 'value'

    before = {'nested': val}
    after = {'nested_two': val*2}

    nested = {'test': {'main': before}}
    new_nested = {'test': {'main': after}, 'NESTED': True}

    cfg = get_config(Config, nested)
    cfg.update(new_nested)

    assert cfg.data['test']['main'] == {**before, **after}, 'not updated'
    assert cfg.data['test']['main']['nested'] == val, 'nested update has failed'


def test_config_update_force(get_config):
    val = 'value'
    nested = {'test': {'main': {'nested': val}}}
    new_nested = {'test': {'main': {'nested_two': val}}, 'FORCE': True}

    cfg = get_config(Config, nested)
    cfg.update(new_nested)

    assert not cfg.data['test']['main'].get('nested')
    assert cfg.data['test']['main'].get('nested_two')


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
    test_keys = ['q_int', 'q_ext', 'q_log', 'ip', 'uid', 'sub', 'pub'] \
                + list(config.keys())
    conf_keys = list(cfg.data.keys())
    test_keys.sort()
    conf_keys.sort()

    assert conf_keys == test_keys, 'inconsistent config keys'


def test_config_system_logger(get_config, default_config):
    """ Test creates SystemConfig logger """
    cfg = get_config(SystemConfig, default_config('sys'))
    logger = cfg.logger_instance

    assert logger.level == logging.INFO, "wrong logging level"
    assert len(logger.handlers) == 3, f"wrong number of logger handlers: {logger.handlers}"
    assert cfg.logger_instance is logger
    assert cfg.log.internal_queue == cfg.get('q_int')
    assert cfg.log.logging_queue == cfg.get('q_log')


def test_config_system_logger_debug(get_config, default_config):
    """ Test creates SystemConfig logger """
    debug_config = {**default_config('sys')}
    debug_config.update(debug=True)
    cfg = get_config(SystemConfig, debug_config)
    logger = cfg.logger_instance


    assert logger.level == logging.DEBUG, "wrong logging level"
    assert len(logger.handlers) == 3, f"wrong number of logger handlers: {logger.handlers}"
    assert cfg.logger_instance is logger
    assert cfg.log.internal_queue == cfg.get('q_int')
    assert cfg.log.logging_queue == cfg.get('q_log')


def test_config_system_logger_fpath(get_config, default_config):
    """ Test creates SystemConfig logger """
    cfg = get_config(SystemConfig, default_config('sys'))
    real_root = os.path.abspath(os.path.dirname(__file__))
    logger = cfg.logger(name='test', level=logging.ERROR)

    assert not cfg.DEBUG, 'sudden debug'
    assert logger.level == logging.ERROR, f"wrong logging level: {logger}"
    for handler in logger.handlers:
        if handler.name == 'file':
            file_path = os.path.join(real_root, 'res', 'messages.log')
        elif handler.name == 'errors':
            file_path = os.path.join(real_root, 'res', 'errors.log')
        else:
            continue
        assert getattr(handler, 'baseFilename') == file_path, f'wrong file path passed to logger handler'


def test_config_process_logger(get_config, default_config):
    """Test making non-root logger"""
    cfg = get_config(SystemConfig, default_config('sys'))
    logger = cfg.logger()
    msg = "there should be only one queue handler"
    assert len(logger.handlers) == 1, f"{msg}: {logger.handlers}"


def test_config_process_logger_external(get_config, default_config):
    """test making non-root logger with external handler"""

    conf = {**default_config('sys')}
    conf.update(external_logging=logging.DEBUG)
    cfg = get_config(SystemConfig, conf)

    logger = cfg.logger()

    msg = "there should be queue handler + external handler, total of 2"
    assert len(logger.handlers) == 2, f"{msg}: {logger.handlers}"


@pytest.mark.parametrize("levelname, levelno", (["DEBUG", logging.DEBUG],
                                                ["INFO", logging.INFO],
                                                ["ERROR", logging.ERROR]))
def test_config_process_logger_external(get_config, default_config, monkeypatch, levelname, levelno):
    """Test sending logging message"""

    int_queue = []
    message = "test"
    conf = {**default_config('sys')}
    conf.update(external_logging=levelno)
    if levelname == 'DEBUG':
        conf.update(debug=True)
    cfg = get_config(SystemConfig, conf)
    monkeypatch.setattr(cfg.log.internal_queue, "put", lambda x: int_queue.append(x))

    assert levelname not in cfg.log.loggers, f'log with name {levelname} already created'
    logger = cfg.logger(levelname)

    try:
        log_call = getattr(logger, levelname.lower())
    except Exception:
        log_call = getattr(logger, 'error')
    log_call(message)
    expected = {"msg": message, "lvl": levelname}

    err = "there should be queue handler + external handler, total of 2"

    assert int_queue, "internal queue has no messages"
    assert len(logger.handlers) == 2, f"{err}: {logger.handlers}"
    assert isinstance(int_queue[0], Event), f"wrong queue content: {int_queue}"
    assert int_queue[0].data == expected, f"wrong data in event: {int_queue[0]}"


def test_config_device_init(get_config, monkeypatch):
    """ Test creates DeviceConfig """
    monkeypatch.setattr(DeviceConfig, 'minimal_essential_conf', {'int': 1})
    cfg = get_config(DeviceConfig, base_config)

    assert isinstance(cfg, DeviceConfig), 'wrong class'
    assert cfg.data == base_config, 'bad config loaded'


def test_config_device_init_with_defaults(get_config, monkeypatch):
    """ Test creates DeviceConfig with minimal essential conf """
    notbase_config = {'not_presented': 1}
    monkeypatch.setattr(DeviceConfig, 'minimal_essential_conf', notbase_config)
    cfg = get_config(DeviceConfig, base_config)

    assert isinstance(cfg, DeviceConfig), 'wrong class'
    assert cfg.data == notbase_config, 'bad config loaded'


@pytest.mark.parametrize('config_dict', (base_config,))
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
    cfg = get_config(DeviceConfig, dict(**test_dict, **base_config.get('int')))

    get_data = cfg.get('blocked')
    cfg.set('blocked', False)

    assert get_data is True, 'bad getter'
    assert cfg.get('blocked') is False, 'bad setter'


@pytest.mark.parametrize('config_dict', (base_config,))
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
    cfg = get_config(DeviceConfig, base_config)
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
    cfg = get_config(DeviceConfig, base_config, fname=fname)
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
    cfg = get_config(DeviceConfig, base_config, fname=fname)
    cfg.save()
    write_config_fixture('<< EOF >>', fname)
    should_be_default = cfg.read()

    assert should_be_default == is_default, 'configs not matched'


@pytest.mark.parametrize('config_dict', (base_config,))
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


@pytest.mark.parametrize('config_dict', (base_config,))
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


@pytest.mark.parametrize('config_dict', (base_config,))
def test_file_lock_busy(get_config, monkeypatch, config_dict):
    """ Test FileLock when file locked """
    cfg = get_config(DeviceConfig, config_dict.get('str'))
    # just ignore time sleep
    monkeypatch.setattr(time, 'sleep', lambda x: None)
    file_lock = FileLock(cfg.config_path, timeout=.1)
    with file_lock:
        file_lock.acquire()
        with pytest.raises(Exception):
            assert cfg.write()
            assert cfg.read()

    # assert res == None, 'lock acquired but should not'
