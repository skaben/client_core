import pytest

from skabenclient.mqtt_client import MQTTClient
from skabenclient.config import SystemConfig

from skabenclient.tests.mock.comms import MockMessage, MockQueue

test_message_content = (
    "topic/uid/command",
    b'{"task_id": "12345", "timestamp": "987654321", "datahold": {"test": "data"}}'
)

@pytest.fixture
def get_client(get_config, default_config):
    system_config = get_config(SystemConfig, default_config('sys'))
    client = MQTTClient(system_config)

    return client, system_config


def test_client_init(get_client):
    client, config = get_client

    for attr in ('q_int', 'q_ext',
                 'pub', 'sub',
                 'broker_ip',
                 'username', 'password'):
        assert getattr(client, attr) == config.get(attr)
    # check broker port default value assignment
    assert client.broker_port == config.get('broker_port', 1883)


def test_client_on_message(get_client, monkeypatch):
    """ very simple hardcoded test """
    client, config = get_client
    mock_queue = MockQueue()
    mock_message = MockMessage(test_message_content)

    monkeypatch.setattr(client, 'q_int', mock_queue)
    client.on_message(client='',
                      userdata='',
                      msg=mock_message)
    message = mock_queue.get()
    data = message.data

    assert message.type == 'mqtt'
    assert message.cmd == 'new'

    for attr in ['topic', 'uid', 'command']:
        assert data.get(attr) == attr
    assert data.get('timestamp') == 987654321
    assert data.get('task_id') == '12345'
    assert isinstance(data.get('datahold'), dict)
    assert data.get('datahold') == {'test': 'data'}

# holy molly I don't want to test paho mqtt connect/reconnect...
