from skabenclient.config import DeviceConfig, SystemConfig
from skabenclient.helpers import make_event


class BaseDevice:

    """ Abstract device handler class.

        Handling user input and end device state.
        All persistent storage operations and server interactions is performed by contexts
    """

    config_class = DeviceConfig

    def __init__(self, system_config, device_config_path):
        if not isinstance(system_config, SystemConfig):
            raise Exception(f'config object is not a SystemConfig, but {type(system_config)} instead')
        # get only necessary from system config
        self.q_int = system_config.get('q_int')
        self.uid = system_config.get('uid')
        self.logger = system_config.logger()
        # assign device ingame config
        self.config = self.config_class(device_config_path)
        self.config.load()  # load and update current running conf

    def run(self):
        """ Abstract method for run device """
        raise NotImplementedError(f"{self} is abstract and cannot be started")

    def state_update(self, data):
        """ Update device configuration from user actions

            When new data from user actions received, check current config and if changed,
            send new event to inner event queue for local config change.
        """
        if not isinstance(data, dict):
            self.logger.error('message type not dict: {}\n{}'.format(type(data), data))
            return
        delta = {}
        for key in data:
            # make diff
            old_value = self.config.get(key, None)
            if data[key] != old_value:
                delta[key] = data[key]
        if delta:
            delta['uid'] = self.uid
            event = make_event('device', 'input', delta)
            self.q_int.put(event)
            return event
        # else do nothing - for mitigating possible loop in q_int 'device'

    def state_reload(self):
        """ Re-read and apply device saved state """
        return self.config.load()

    def send_message(self, data):
        """ Send message to server """
        event = make_event('device', 'send', data)
        self.q_int.put(event)
        return event
