import time
import pytest
import skabenproto as skpt
import skabenclient.managers as mgr

from skabenclient.config import SystemConfig, DeviceConfig
from skabenclient.device import BaseHandler
from skabenclient.helpers import make_event


def test_base_manager(get_config, default_config):
    syscfg = get_config(SystemConfig, default_config('sys'))
    base = mgr.BaseManager(syscfg)

    for key in ['uid', 'ip', 'q_int', 'q_ext']:
        assert key in base.sys_conf.keys(), f'missing {key}'
        assert base.sys_conf.get(key) is not None, f'missing value for {key}'
    assert base.reply_channel == 'test' + 'ask'


class MockMessage:

    def __init__(self, packet):
        self.topic = str(packet[0])
        self.payload = bytes(packet[1], 'utf-8')


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
    """ Test update command """
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
    """ Test send command """
    syscfg = event_setup
    _dict = {'new_value': 'new'}
    event = make_event('device', 'send', _dict)

    with mgr.EventManager(syscfg) as manager:
        monkeypatch.setattr(manager, 'send_config', lambda x: x)
        result = manager.manage(event)

    test_conf = syscfg.get('device').config.load()

    assert test_conf.get('new_value') is None, 'config saved when should not'
    assert result == _dict, 'bad data sent'


def test_event_manager_input(event_setup, monkeypatch, default_config):
    """ Test input command """
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
    """ Test reload command """
    syscfg = event_setup
    dev_conf = syscfg.get('device').config

    pre_conf = dev_conf.load()
    changed = dev_conf.update({'value': 'updated'})
    event = make_event('device', 'reload')

    with mgr.EventManager(syscfg) as manager:
        result = manager.manage(event)

    assert changed.get('value') == 'updated', 'config not updated on the fly'
    assert result == pre_conf, 'config was not reloaded'


def test_event_manager_send_config(event_setup, monkeypatch, default_config):
    """ Test send config to server """
    syscfg = event_setup
    device = syscfg.get('device')
    _dict = {'new_value': 'newvalue'}

    with mgr.EventManager(syscfg) as manager:
        in_queue = list()
        monkeypatch.setattr(manager.q_ext, 'put', lambda x: in_queue.append(x))
        manager.send_config(_dict)
        message = MockMessage(in_queue[-1])
        device_type = manager.dev_type
        with skpt.PacketDecoder() as decoder:
            result = decoder.decode(message)

    assert result.get('command') == 'SUP', 'wrong command'
    assert result.get('uid') == device.uid, 'wrong device UID'
    assert result.get('dev_type') == device_type, 'wrong device type'
    assert result['payload'].get('ts') == 0, 'wrong device timestamp'
    assert result['payload'].get('new_value') == _dict.get('new_value', 1), 'bad data send'


def test_event_manager_send_config_filtered(event_setup, monkeypatch, default_config):
    """ Test send config to server """
    syscfg = event_setup
    device = syscfg.get('device')
    device.filtered_keys.extend(['filtered'])
    _dict = {'new_value': 'newvalue', 'filtered': True}

    with mgr.EventManager(syscfg) as manager:
        in_queue = list()
        monkeypatch.setattr(manager.q_ext, 'put', lambda x: in_queue.append(x))
        manager.send_config(_dict)
        message = MockMessage(in_queue[-1])
        with skpt.PacketDecoder() as decoder:
            result = decoder.decode(message)

    assert result['payload'].get('new_value') == 'newvalue', 'data not sent'
    assert result['payload'].get('filtered') is not True, 'filtered data sent'

