import os
import yaml
import pytest
import sqlite3

root_dir = os.path.dirname(os.path.abspath(__file__))

@pytest.fixture(scope="module")
def get_root():
    return root_dir


@pytest.fixture(scope="module")
def write_config():

    def _dec(config):
        stream = os.popen("ip route | grep 'default' | sed -nr 's/.*dev ([^\ ]+).*/\\1/p'")
        iface_name = stream.read()
        config_dict = {"iface": iface_name.rstrip()}
        config_dict.update(config)
        write_to = os.path.join(root_dir, "res", "config.yml")
        with open(write_to, "w") as file:
            yaml.dump(config_dict, file)
        return write_to

    return _dec


@pytest.fixture(scope="module")
def make_db(request):
    path_to_db = str(os.path.join(root_dir, 'res', f'test.db'))
    sqlite3.connect(path_to_db)
    def _finalize():
        os.remove(path_to_db)
    request.addfinalizer(_finalize)
    return path_to_db
