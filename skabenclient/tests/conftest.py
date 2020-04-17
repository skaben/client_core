import os
import yaml
import pytest

root_dir = os.path.dirname(os.path.abspath(__file__))

@pytest.fixture(scope="module")
def get_root():
    return root_dir


def _iface():
    stream = os.popen("ip route | grep 'default' | sed -nr 's/.*dev ([^\ ]+).*/\\1/p'")
    iface_name = stream.read()
    return iface_name.rstrip()


@pytest.fixture(scope="module")
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


@pytest.fixture(scope="module")
def write_config_fixture():

    def _wrap(config, fname):
        return write_config(config, fname)

    return _wrap


@pytest.fixture(scope="module")
def get_config(request):

    def _wrap(config_obj, config_dict, **kwargs):
        path = write_config(config_dict, kwargs.get('fname', 'not_named.yml'))
        config = config_obj(path)

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
def get_empty_config(request):

    def _wrap(config_obj, path):
        config = config_obj(path)

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

#TODO: config collection


@pytest.fixture(scope="module")
def default_config():

    _sys = {
        "dev_type": "test",
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