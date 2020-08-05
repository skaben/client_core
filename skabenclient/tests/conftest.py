import os
import yaml
import pytest
import hashlib

from skabenclient.config import LOGGERS

root_dir = os.path.dirname(os.path.abspath(__file__))

@pytest.fixture(scope="module")
def get_root():
    return root_dir


def _iface():
    stream = os.popen("ip route | grep 'default' | sed -nr 's/.*dev ([^\ ]+).*/\\1/p'")
    iface_name = stream.read()
    return iface_name.rstrip()


@pytest.fixture()
def get_iface():
    return _iface()


def write_config(config, fname):
    path = os.path.join(root_dir, "res", fname)
    try:
        with open(path, "w") as file:
            yaml.dump(config, file)
        return path
    except Exception:
        raise


def make_object(obj, path):
    return obj(path)


@pytest.fixture()
def write_config_fixture():

    def _wrap(config, fname):
        return write_config(config, fname)

    return _wrap


@pytest.fixture()
def get_config(request):

    def _wrap(config_obj, config_dict, **kwargs):
        path = write_config(config_dict, kwargs.get('fname', 'not_named.yml'))
        config = make_object(config_obj, path)

        def _td():
            try:
                os.remove(path)
                os.remove(f"{path}.lock")
            except FileNotFoundError:
                pass
            except Exception:
                raise

        request.addfinalizer(_td)
        return config

    return _wrap


@pytest.fixture()
def get_empty_config(request):

    def _wrap(config_obj, path):
        config = make_object(config_obj, path)

        def _td():
            try:
                os.remove(path)
                os.remove(f"{path}.lock")
            except FileNotFoundError:
                pass
            except Exception:
                raise

        request.addfinalizer(_td)
        return config

    return _wrap


@pytest.fixture(scope="module")
def default_config():

    _sys = {
        "topic": "test",
        "test": "test",
        "name": "main",
        "broker_ip": "127.0.0.1",
        "iface": _iface()
    }

    _dev = {'bool': True,
            'int': 1,
            'float': 0.1,
            'string': 'abcd',
            'list': [1, 'str', 0.1]}

    switch = {
        'sys': _sys,
        'dev': _dev
    }

    def _wrap(conf_type):
        return switch.get(conf_type)

    return _wrap


@pytest.fixture()
def get_hash():

    def _wrap(data):
        encoded = data.encode('utf-8')
        hash = hashlib.md5()
        hash.update(encoded)
        hash = hash.hexdigest()
        return hash

    return _wrap
