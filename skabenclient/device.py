from skabenclient.config import DeviceConfig, SystemConfig
from skabenclient.helpers import make_event


class BaseDevice:

    """ Abstract device handler class.

        Handling user input and end device state.
        All persistent storage operations and server interactions is performed by contexts
    """

    config_class = DeviceConfig

    def __init__(self, app_config, device_config):
        if not isinstance(app_config, SystemConfig):
            raise Exception(f'app_config is not a SystemConfig, but {type(app_config)} instead')
        if not isinstance(device_config, self.config_class):
            raise Exception(f'device_config is not a {self.config_class}, but {type(device_config)} instead')
        # assign system config
        self.system = app_config
        self.q_int = app_config.get('q_int')
        self.uid = app_config.get('uid')
        self.logger = app_config.logger()
        # assign device ingame config
        self.config = device_config
        self.config.load()  # load and update current running conf

    def run(self):
        print('application is starting...')
        self.logger.debug(f'device starting as: {self.system} \n {self.config}')
        reload_event = make_event('device', 'reload')
        self.q_int.put(reload_event)

    def stop(self):
        print('device is stopping...')
        self.logger.debug(f"stopping device {self}")
        end_event = make_event("exit")
        self.q_int.put(end_event)

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

    def state_reload(self):
        """ Re-read and apply device saved state """
        return self.config.load()

    def send_message(self, data):
        """ Send message to server """
        event = make_event('device', 'info', data)
        self.q_int.put(event)
        return event
