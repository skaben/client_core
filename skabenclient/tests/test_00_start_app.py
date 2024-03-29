import logging
import threading
import time
from queue import Queue

import pytest

from skabenclient.config import DeviceConfig, SystemConfig
from skabenclient.contexts import EventContext, Router
from skabenclient.device import BaseDevice
from skabenclient.helpers import make_event
from skabenclient.main import start_app
from skabenclient.mqtt_client import MQTTClient


@pytest.fixture
def get_router(get_config, default_config):
    # write device config
    devcfg = get_config(DeviceConfig,
                        default_config('dev'),
                        fname='test_cfg.yml')
    devcfg.save()
    # write system config with device config file location
    syscfg = get_config(SystemConfig, default_config('sys'), fname='sys_cfg.yml')
    # create device from system config
    device = BaseDevice(syscfg, devcfg)
    # assign device instance to config singleton
    syscfg.update({'device': device})
    router = Router(syscfg)

    return router, syscfg, devcfg


@pytest.fixture
def get_from_queue():

    def _wrap(queue):
        idx = 0
        while not idx >= 10:
            if not queue.empty():
                yield queue.get()
            else:
                idx += 1
                time.sleep(.1)

    return _wrap


@pytest.fixture(autouse=True)
def cleanup_logger_handlers():
    yield
    loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    loggers.append(logging.getLogger())  # add root logger to list
    [logger.handlers.clear() for logger in loggers]


"""
def test_router_init(get_router):
    router, syscfg, devcfg = get_router
    for attr in ('q_int', 'q_ext'):
        assert hasattr(router, attr), f'missing attribute: {attr}'
    for attr in ('q_int', 'q_ext'):
        assert getattr(router, attr) == syscfg.data[attr], f"wrong value for {attr}"

    assert router.logger, "logger was not created"
"""


def test_start_app_routine(get_config, default_config, get_from_queue, monkeypatch):
    """ Test all client components was initialized and can be start successfully """
    # write device config
    devcfg = get_config(DeviceConfig, default_config('dev'), fname='test_cfg.yml')
    devcfg.save()
    # write system config with device config file location
    syscfg = get_config(SystemConfig, default_config('sys'))
    # create device from system config
    device = BaseDevice(syscfg, devcfg)
    syscfg.update({'device': device})

    test_queue = Queue()

    # Mqtt client is a process, monkeypatching "run" method not working because of it
    monkeypatch.setattr(MQTTClient, 'start', lambda *a: test_queue.put('mqtt'))
    monkeypatch.setattr(Router, 'run', lambda *a: test_queue.put('router'))
    # BaseDevice is not a threading interface at all, so no join later
    monkeypatch.setattr(BaseDevice, 'run', lambda *a: test_queue.put('device'))

    monkeypatch.setattr(MQTTClient, 'join', lambda *a: True)
    monkeypatch.setattr(Router, 'join', lambda *a: True)

    start_app(app_config=syscfg, device=device)

    result = list(get_from_queue(test_queue))
    for service in ['mqtt', 'router', 'device']:
        assert service in result, f'{service} not started'


@pytest.mark.skip(reason="bad queue timings management")
def test_router_start_stop(get_router, monkeypatch, caplog):
    router, syscfg, devcfg = get_router

    router.start()
    assert threading.active_count() == 2, 'bad number of threads'
    router.stop()
    assert router.running is False, 'router not stopped'
    router.join(.1)
    assert threading.active_count() == 1, 'seems like thread was not exited'


def test_router_exit_by_event(get_router, request, get_from_queue):
    router, syscfg, devcfg = get_router
    router.start()

    def _fin():
        router.running = False
        router.join(.1)

    request.addfinalizer(_fin)

    event = make_event('exit')
    syscfg.data['q_int'].put(event)
    expected_event = list(get_from_queue(syscfg.get('q_ext')))

    assert expected_event, 'cannot get event from external queue'
    assert expected_event[0].type == 'exit', 'external message not sent'
    time.sleep(1)
    assert router.running is False, 'router was not stopped'


def test_router_event_mqtt(get_router, monkeypatch, get_from_queue):
    router, syscfg, devcfg = get_router
    test_queue = Queue()
    monkeypatch.setattr(EventContext, 'manage_mqtt', lambda x, y: test_queue.put(y))
    router.start()

    kinda_mqtt_parsed_message = {'datahold': {'data': 'test'}, 'command': 'PING'}
    event = make_event('mqtt', 'test', kinda_mqtt_parsed_message)
    syscfg.get('q_int').put(event)
    result = list(get_from_queue(test_queue))

    assert result, 'event not managed'
    assert not len(result) > 1, 'too many events'
    assert result[0].data.get('command') == 'PING'
    assert result[0].data.get('datahold') == {'data': 'test'}


@pytest.mark.parametrize('event_data', ({'dict': 'data'}, None))
def test_router_event_device(get_router, monkeypatch, get_from_queue, event_data):
    router, syscfg, devcfg = get_router
    test_queue = Queue()
    monkeypatch.setattr(EventContext, 'manage', lambda x, y: test_queue.put(y))
    router.start()

    event = make_event('device', 'test', event_data)
    syscfg.get('q_int').put(event)
    result = list(get_from_queue(test_queue))

    assert result, 'event not managed'
    assert not len(result) > 1, 'too many events'
    assert result[0].type == 'device'
    assert result[0].cmd == 'test'
    assert result[0].data == event_data
