import pytest

from skabenclient.tests.mock.logger import MockLogger

from skabenclient.device import BaseDevice
from skabenclient.helpers import make_event
from skabenclient.config import SystemConfig, DeviceConfig


@pytest.fixture
def get_device(get_config, default_config, monkeypatch):
    devcfg = get_config(DeviceConfig, default_config('dev'), fname='test_cfg.yml')
    devcfg.save()

    syscfg = get_config(SystemConfig, default_config('sys'))
    device = BaseDevice(syscfg, devcfg.config_path)
    monkeypatch.setattr(device, 'logger', MockLogger)

    return device, devcfg, syscfg


def test_device_init(get_device):
    device, devcfg, syscfg = get_device

    assert devcfg.config_path != syscfg.config_path
    assert isinstance(device.config, DeviceConfig), 'wrong instance'
    assert device.config.config_path == devcfg.config_path, 'wrong config path'
    assert device.config.data == devcfg.data


def test_device_input_new(get_device, default_config):
    device, devcfg, syscfg = get_device
    new_input = {'input': 'new_input'}

    event = device.state_update({**default_config('dev'), **new_input})
    test_event = make_event('device', 'input',
                            {**new_input, **{'uid': syscfg.get('uid')}})  # add uid
    #device.config.save()
    #assert device.config.data == {**devcfg.data, **new_input}, 'user input not saved'
    assert event.type == test_event.type, 'bad event type'
    assert event.cmd == test_event.cmd, 'bad event command'
    assert event.data == test_event.data, 'bad event data'


def test_device_input_exist(get_device, default_config):
    device, devcfg, syscfg = get_device
    new_input = default_config('dev')
    event = device.state_update(new_input)
#    device.config.save()
#    assert device.config.data == {**devcfg.data, **new_input}, 'user input not saved'
    assert event is None, "event created when should not"


def test_device_input_send_msg(get_device, default_config):
    device, devcfg, syscfg = get_device

    event = device.send_message(default_config('dev'))
    test_event = make_event('device', 'send', default_config('dev'))

    assert event.type == test_event.type, 'bad event type'
    assert event.cmd == test_event.cmd, 'bad event command'
    assert event.data == test_event.data, 'bad event data'
