import skabenclient.managers as mgr
import skabenclient.mqtt_client as mqtt
from skabenclient.config import Config

TEST_CFG = {
    'dev_type': 'test',
}

def test_base_manager(write_config):
    path = write_config(TEST_CFG)
    config = Config(path)
    base = mgr.BaseManager(config)
    
    assert base.reply_channel == TEST_CFG['dev_type'] + 'ask'
