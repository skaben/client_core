import pytest
import skabenclient.managers as mgr

from skabenclient.config import SystemConfig, DeviceConfig
from skabenclient.device import BaseHandler
from skabenclient.helpers import make_event


def test_base_manager(get_config):
    config = get_config(SystemConfig, {'dev_type': 'test', "iface": "eth0"})
    base = mgr.BaseManager(config)

    assert base.config == config.data, 'wrong config load'
    assert base.reply_channel == 'test' + 'ask'


@pytest.fixture
def event_setup(get_config, default_config):
    devcfg = get_config(DeviceConfig, default_config('dev'), 'test_cfg.yml')
    devcfg.save()

    dev_dict = {**default_config('sys'), **{'device_file': devcfg.config_path}}
    syscfg = get_config(SystemConfig, dev_dict, 'system_conf.yml')

    handler = BaseHandler(syscfg)

    syscfg.set('device', handler)

    return syscfg


def test_event_manager_update(event_setup, monkeypatch):
    syscfg = event_setup
    event = make_event('device', 'update', {'value': 'newval',
                                            'task_id': 123123})
    syscfg.get('device').config.set('value', 'oldval')
    syscfg.get('device').config.save()

    with mgr.EventManager(syscfg) as manager:
        monkeypatch.setattr(manager, 'confirm_update', lambda *args: {'task_id': args[0],
                                                                      'response': args[1]})
        result = manager.manage(event)

    test_conf = syscfg.get('device').config.load()

    assert result.get('response') == 'ACK'
    assert result.get('task_id') == 123123
    assert test_conf.get('value') == 'newval'


def test_event_manager_send(event_setup, monkeypatch, default_config):
    syscfg = event_setup
    _dict = {'new_value': 'new'}
    event = make_event('device', 'send', _dict)

    with mgr.EventManager(syscfg) as manager:
        monkeypatch.setattr(manager, 'send_config', lambda x: x)
        result = manager.manage(event)

    test_conf = syscfg.get('device').config.load()

    assert test_conf.get('new_value') is None, 'config saved when should not'
    assert result == _dict, 'bad data send'


def test_event_manager_input(event_setup, monkeypatch, default_config):
    syscfg = event_setup
    _dict = {'new_value': 'new'}
    event = make_event('device', 'input', _dict)

    with mgr.EventManager(syscfg) as manager:
        monkeypatch.setattr(manager, 'send_config', lambda x: x)
        result = manager.manage(event)

    post_conf = {**default_config('dev'), **_dict}

    assert result == _dict, 'config not sent'
    assert syscfg.get('device').config.load() == post_conf, 'config not saved'


def test_event_manager_reload(event_setup, default_config):
    syscfg = event_setup
    dev_conf = syscfg.get('device').config

    pre_conf = dev_conf.load()
    changed = dev_conf.update({'value': 'updated'})
    event = make_event('device', 'reload')

    with mgr.EventManager(syscfg) as manager:
        result = manager.manage(event)

    assert changed.get('value') == 'updated', 'config not updated on the fly'
    assert result == pre_conf, 'config was not reloaded'
