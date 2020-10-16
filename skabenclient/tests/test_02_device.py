import pytest

from skabenclient.tests.mock.logger import MockLogger
from skabenclient.tests.mock.data import base_config, yaml_content_as_dict

from skabenclient.device import BaseDevice
from skabenclient.helpers import make_event
from skabenclient.config import SystemConfig, DeviceConfig


test_complex_dict = {"complex": yaml_content_as_dict}


@pytest.fixture
def get_device(get_config, default_config, monkeypatch):
    devcfg = get_config(DeviceConfig, default_config('dev'), fname='test_cfg.yml')
    devcfg.save()

    syscfg = get_config(SystemConfig, default_config('sys'))
    device = BaseDevice(syscfg, devcfg)
    monkeypatch.setattr(device, 'logger', MockLogger)

    return device, devcfg, syscfg


def test_device_init(get_device):
    device, devcfg, syscfg = get_device

    assert devcfg.config_path != syscfg.config_path
    assert isinstance(device.config, DeviceConfig), 'wrong instance'
    assert device.config.config_path == devcfg.config_path, 'wrong config path'
    assert device.config.data == devcfg.data


@pytest.mark.parametrize("payload", (base_config, yaml_content_as_dict, test_complex_dict))
def test_device_input_new(get_device, default_config, payload):
    device, devcfg, syscfg = get_device

    event = device.state_update({**default_config('dev'), **payload})
    payload_and_uid = {**payload, **{'uid': syscfg.get('uid')}}
    test_event = make_event('device', 'input', payload_and_uid)
    device.config.save(payload)

    assert device.config.data == {**devcfg.data, **payload}, 'user input not saved'
    assert event.type == test_event.type, 'bad event type'
    assert event.cmd == test_event.cmd, 'bad event command'
    assert event.data == test_event.data, 'bad event data'


@pytest.mark.parametrize("payload", (base_config, yaml_content_as_dict))
def test_device_input_exist(get_device, default_config, payload):
    device, devcfg, syscfg = get_device
    device.config.data = payload
    event = device.state_update(payload)
    device.config.save(payload)
    assert device.config.data == {**devcfg.data, **payload}, 'user input not saved'
    assert event is None, "event created when should not"


def test_device_input_send_msg(get_device, default_config):
    device, devcfg, syscfg = get_device

    event = device.send_message(default_config('dev'))
    test_event = make_event('device', 'info', default_config('dev'))

    assert event.type == test_event.type, 'bad event type'
    assert event.cmd == test_event.cmd, 'bad event command'
    assert event.data == test_event.data, 'bad event data'
