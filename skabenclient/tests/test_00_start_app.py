import time
import threading
import pytest

from skabenclient.main import Router, start_app
from skabenclient.device import BaseDevice
from skabenclient.config import SystemConfig, DeviceConfig

# TODO: git gud at threads testing

@pytest.fixture
def get_router(get_config, default_config):
    # write device config
    devcfg = get_config(DeviceConfig, default_config('dev'), 'test_cfg.yml')
    devcfg.save()
    # write system config with device config file location
    _cfg = {**default_config('sys'),
            **{'device_file': devcfg.config_path}}
    syscfg = get_config(SystemConfig, _cfg)
    # create device from system config
    device = BaseDevice(syscfg)
    # assign device instance to config singleton
    syscfg.set('device', device)
    router = Router(syscfg)
    return router, syscfg, devcfg


def test_router_init(get_router):
    router, syscfg, devcfg = get_router
    for attr in ('q_int', 'q_ext', 'device'):
        assert hasattr(router, attr), f'missing attribute: {attr}'
        assert getattr(router, attr) == syscfg.data[attr], f"wrong value for {attr}"

    assert router.logger, "logger was not created"


def test_router_start(get_router, monkeypatch, request, caplog):
    router, syscfg, devcfg = get_router
    monkeypatch.setattr(time, 'sleep', lambda x: True)
    router.start()

    def _fin():
        router.running = False
        router.join(.1)

    request.addfinalizer(_fin)

    assert threading.active_count() == 2, 'bad number of threads'


def test_router_run(get_router, request):
    router, syscfg, devcfg = get_router
    router.run()
    assert router.running is True
    router.running = False

    def _fin():
        router.running = False
        router.join(.1)

    request.addfinalizer(_fin)


@pytest.mark.skip(reason="bad thread management")
def test_router_stop(get_router, monkeypatch, request):
    """ Test router stop method """
    router, syscfg, devcfg = get_router

    def mock_run():
        while router.running:
            time.sleep(.1)

    def _fin():
        router.running = False
        router.join(.1)

    request.addfinalizer(_fin)

    monkeypatch.setattr(router, 'run', mock_run)
    router.start()
    assert router.running is True, 'router not running'

    router.stop()
    assert router.running is False, 'router still running'
