import os
import yaml
import pytest
import sqlite3

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


def write_config(config, path=None):
    if not path:
        path = os.path.join(root_dir, "res", "test_config.yml")
    try:
        with open(path, "w") as file:
            yaml.dump(config, file)
        return path
    except Exception:
        raise


@pytest.fixture(scope="module")
def get_config(request):

    def _wrap(config_obj, config_dict):
        path = write_config(config_dict)
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
