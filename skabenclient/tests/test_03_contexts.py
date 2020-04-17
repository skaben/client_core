import pytest
import json

import skabenproto as sk
import skabenclient.contexts as mgr

from skabenclient.config import SystemConfig, DeviceConfig
from skabenclient.device import BaseDevice
from skabenclient.helpers import make_event


def test_base_context(get_config, default_config):
    syscfg = get_config(SystemConfig, default_config('sys'))
    base = mgr.BaseContext(syscfg)

    for key in ['uid', 'ip', 'q_int', 'q_ext', 'listen', 'publish']:
        assert key in base.config.data.keys(), f'missing {key}'
        assert base.config.get(key) is not None, f'missing value for {key}'


class MockMessage:

    def __init__(self, packet):
        self.topic = packet[0]
        self.payload = packet[1]

        self.decoded = json.loads(self.payload.decode('utf-8'))
        self.dev_type, self.uid, self.command = self.topic.split('/')


@pytest.fixture
def event_setup(get_config, default_config):

    def _wrap(sys_config=None, dev_config=None):
        if not sys_config:
            sys_config = default_config('sys')
        if not dev_config:
            dev_config = default_config('dev')

        devcfg = get_config(DeviceConfig, dev_config, fname='test_cfg.yml')
        devcfg.save()

        syscfg = get_config(SystemConfig, sys_config, fname='system_conf.yml')
        device = BaseDevice(syscfg, devcfg.config_path)
        syscfg.set('device', device)
        return syscfg

    return _wrap


def test_event_extended_dict(event_setup, default_config, monkeypatch):
    dev_dict = {**default_config('dev'), **{'test_key': "test_val"}}
    syscfg = event_setup(dev_config=dev_dict)

    assert syscfg.get('device').config.data == dev_dict, 'not loaded'


def test_event_context_update(event_setup, monkeypatch):
    """ Test update command """
    syscfg = event_setup()
    event = make_event('device', 'update', {'value': 'newval',
                                            'task_id': 123123})
    syscfg.get('device').config.set('value', 'oldval')
    syscfg.get('device').config.save()

    with mgr.EventContext(syscfg) as context:
        monkeypatch.setattr(context, 'confirm_update', lambda *args: {'task_id': args[0],
                                                                      'response': args[1]})
        result = context.manage(event)

    devconf = syscfg.get('device').config
    # devconf.reset()  # clean up config namespace
    test_conf = devconf.load()  # reread from file

    assert result.get('response') == 'ACK'
    assert result.get('task_id') == 123123
    assert test_conf.get('value') == 'newval'


def test_event_context_send(event_setup, monkeypatch, default_config):
    """ Test send command """
    syscfg = event_setup()
    _dict = {'new_value': 'new'}
    event = make_event('device', 'send', _dict)

    with mgr.EventContext(syscfg) as context:
        monkeypatch.setattr(context, 'send_config', lambda x: x)
        result = context.manage(event)

    test_conf = syscfg.get('device').config.load()

    assert test_conf.get('new_value') is None, 'config saved when should not'
    assert result == _dict, 'bad data sent'


def test_event_context_input(event_setup, monkeypatch, default_config):
    """ Test input command """
    syscfg = event_setup()
    _dict = {'new_value': 'new'}
    event = make_event('device', 'input', _dict)

    with mgr.EventContext(syscfg) as context:
        # not sending config anywhere, just calling device.config.save
        monkeypatch.setattr(context, 'send_config', lambda x: x)
        result = context.manage(event)

    post_conf = {**default_config('dev'), **_dict}

    assert result == _dict, 'config not sent'
    assert syscfg.get('device').config.load() == post_conf, 'config not saved'


def test_event_context_reload(event_setup, default_config):
    """ Test reload command """
    syscfg = event_setup()
    dev_conf = syscfg.get('device').config

    pre_conf = dev_conf.load()
    changed = dev_conf.update({'value': 'updated'})
    event = make_event('device', 'reload')

    with mgr.EventContext(syscfg) as context:
        result = context.manage(event)

    assert changed.get('value') == 'updated', 'config not updated on the fly'
    assert result == pre_conf, 'config was not reloaded'

#todo: fix fix fix

def test_event_context_send_config(event_setup, monkeypatch, default_config):
    """ Test send config to server """
    in_queue = list()
    syscfg = event_setup()
    device = syscfg.get('device')
    _dict = {'new_value': 'newvalue'}

    with mgr.EventContext(syscfg) as context:
        device_type = context.dev_type
        monkeypatch.setattr(context.q_ext, 'put', lambda x: in_queue.append(x))
        context.send_config(_dict)
        message = MockMessage(in_queue[-1])

    assert message.dev_type == device_type, 'wrong device type'
    assert message.uid == device.uid, 'wrong device UID'
    assert message.command == 'SUP', 'wrong command'
    assert message.decoded.get('timestamp') == 0, f'wrong device timestamp {message.decoded}'
    assert message.decoded['datahold'].get('new_value') == _dict.get('new_value'), f'bad data send: {message.decoded}'


def test_event_context_send_config_filtered(event_setup, monkeypatch, default_config):
    """ Test send config to server """
    syscfg = event_setup()
    _dict = {'new_value': 'newvalue', 'filtered': True}

    with mgr.EventContext(syscfg) as context:
        in_queue = list()
        context.filtered_keys.extend(['filtered'])
        monkeypatch.setattr(context.q_ext, 'put', lambda x: in_queue.append(x))
        context.send_config(_dict)
        message = MockMessage(in_queue[-1])

    assert message.decoded['datahold'].get('new_value') == 'newvalue', 'data not sent'
    assert message.decoded['datahold'].get('filtered') is not True, 'filtered data sent'


def test_event_context_config_reply(event_setup, default_config, monkeypatch):
    syscfg = event_setup()
    with mgr.EventContext(syscfg) as context:
        in_queue = list()
        monkeypatch.setattr(context.q_ext, 'put', lambda x: in_queue.append(x))
        context.config_reply()
        message = MockMessage(in_queue[-1])

    assert message.decoded['datahold'].get('request') == 'all'


def test_event_context_config_reply_keys(event_setup, default_config, monkeypatch):
    dev_dict = {**default_config('dev'), **{'test_key': 'test_value', 'task_id': '12345'}}
    syscfg = event_setup(dev_config=dev_dict)
    _keys = ['test_key']

    with mgr.EventContext(syscfg) as context:
        in_queue = list()
        monkeypatch.setattr(context.q_ext, 'put', lambda x: in_queue.append(x))
        context.config_reply(keys=_keys)
        message = MockMessage(in_queue[-1])
        config_data = context.device.config.current()

        assert config_data.get('test_key') == dev_dict.get('test_key')
        assert message.decoded['datahold'].get('request') == _keys


@pytest.mark.parametrize('cmd', ('ACK', 'NACK',))
def test_event_context_confirm_update_ack(event_setup, default_config, monkeypatch, cmd):
    dev_dict = {**default_config('dev'), **{'test_key': 'test_value', 'task_id': '12345'}}
    syscfg = event_setup(dev_config=dev_dict)
    _task_id = '123456'

    with mgr.EventContext(syscfg) as context:
        in_queue = list()
        monkeypatch.setattr(context.q_ext, 'put', lambda x: in_queue.append(x))
        context.confirm_update(packet_type=cmd, task_id=_task_id)
        message = MockMessage(in_queue[-1])

        assert message.command == cmd
        assert message.decoded.get('task_id') == _task_id
