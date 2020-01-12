from multiprocessing import Queue
from skabenclient.tests.mock.logger import MockLogger

from skabenclient.device import BaseDevice
from skabenclient.helpers import make_event
from skabenclient.config import SystemConfig, DeviceConfig


def test_handler_init(get_config, default_config):
    devcfg = get_config(DeviceConfig, {'device': 'test'}, 'test_cfg.yml')
    devcfg.save()
    dev_dict = {'device_file': devcfg.config_path}

    appcfg = get_config(SystemConfig,
                        {**default_config('sys'), **dev_dict},
                        'system_conf.yml')
    handler = BaseDevice(appcfg)

    assert devcfg.config_path != appcfg.config_path
    assert isinstance(handler.config, DeviceConfig), 'wrong instance'
    assert handler.config.config_path == devcfg.config_path, 'wrong config path'
    assert handler.config.data == devcfg.data


def test_handler_input_new(get_config, default_config, monkeypatch):
    devcfg = get_config(DeviceConfig, default_config('dev'), 'test_cfg.yml')
    devcfg.save()

    _cfg = {**default_config('sys'),
            **{'device_file': devcfg.config_path}}
    syscfg = get_config(SystemConfig, _cfg)
    handler = BaseDevice(syscfg)
    monkeypatch.setattr(handler, 'logger', MockLogger)

    new_input = {'input': 'new_input'}

    event = handler.state_update({**default_config('dev'), **new_input})
    test_event = make_event('device', 'input',
                            {**new_input, **{'uid': syscfg.get('uid')}})  # add uid
    #handler.config.save()
    #assert handler.config.data == {**devcfg.data, **new_input}, 'user input not saved'
    assert event.type == test_event.type, 'bad event type'
    assert event.cmd == test_event.cmd, 'bad event command'
    assert event.data == test_event.data, 'bad event data'


def test_handler_input_exist(get_config, default_config, monkeypatch):
    devcfg = get_config(DeviceConfig, default_config('dev'), 'test_cfg.yml')
    devcfg.save()

    _cfg = {**default_config('sys'),
            **{'device_file': devcfg.config_path}}
    syscfg = get_config(SystemConfig, _cfg)
    handler = BaseDevice(syscfg)
    monkeypatch.setattr(handler, 'logger', MockLogger)

    new_input = default_config('dev')
    event = handler.state_update(new_input)
#    handler.config.save()
#    assert handler.config.data == {**devcfg.data, **new_input}, 'user input not saved'
    assert event is None, "event created when should not"


def test_handler_input_send_msg(get_config, default_config, monkeypatch):
    devcfg = get_config(DeviceConfig, default_config('dev'), 'test_cfg.yml')
    devcfg.save()

    _cfg = {**default_config('sys'),
            **{'device_file': devcfg.config_path}}
    syscfg = get_config(SystemConfig, _cfg)
    handler = BaseDevice(syscfg)
    monkeypatch.setattr(handler, 'logger', MockLogger)

    event = handler.send_message(default_config('dev'))
    test_event = make_event('device', 'send', default_config('dev'))

    assert event.type == test_event.type, 'bad event type'
    assert event.cmd == test_event.cmd, 'bad event command'
    assert event.data == test_event.data, 'bad event data'
