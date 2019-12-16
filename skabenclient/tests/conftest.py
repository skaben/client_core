import os
import yaml
import pytest

root_dir = os.path.dirname(os.path.abspath(__file__))

@pytest.fixture(scope="module")
def write_config():

    def _decor(config):
        stream = os.popen("ip route | grep 'default' | sed -nr 's/.*dev ([^\ ]+).*/\\1/p'")
        iface_name = stream.read()
        config_dict = {"iface": iface_name.rstrip()}
        config_dict.update(config)
        write_to = os.path.join(root_dir, "res", "config.yml")
        with open(write_to, "w") as file:
            yaml.dump(config_dict, file)
        return write_to

    return _decor
