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


def test_event_manager(get_config, default_config, monkeypatch):
    devcfg = get_config(DeviceConfig, default_config('dev'), 'test_cfg.yml')
    devcfg.save()

    dev_dict = {**default_config('sys'), **{'device_file': devcfg.config_path}}
    syscfg = get_config(SystemConfig, dev_dict, 'system_conf.yml')

    handler = BaseHandler(syscfg)
    handler.config.set('value', 'oldval')
    handler.config.save()

    syscfg.set('device', handler)

    update_event = make_event('device', 'update', {'value': 'newval'})

    with mgr.EventManager(syscfg) as manager:
        monkeypatch.setattr(manager, 'confirm_update', lambda *args: {'task_id': args[0],
                                                                      'response': args[1]})
        result = manager.manage(update_event)

    assert result.get('response') == 'ACK'
    assert handler.config.get('value') == 'newval'
