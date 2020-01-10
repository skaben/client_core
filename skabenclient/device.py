from skabenclient.config import DeviceConfig
from skabenclient.helpers import make_event


class BaseHandler:

    """ Abstract device handler class

        Provides:
        - internal event queue for events from user input

    """

    def __init__(self, system_config):
        self.config = DeviceConfig(system_config.get('device_file'))
        self.config.load()
        self.q_int = system_config.get('q_int')
        self.uid = system_config.get('uid')
        self.logger = system_config.logger()

    def user_input(self, data):
        """ Update device configuration from user actions """
        if not isinstance(data, dict):
            self.logger.error('message type not dict: {}\n{}'.format(type(data), data))
            return
        # self.config.set('alert', 0)  # resetting alert # TODO: what's happening here??
        # delta_keys used later for sending package to server
        delta = {}
        self.logger.debug('plot was {}'.format(self.config))
        for key in data:
            # make diff
            old_value = self.config.get(key, None)
            if data[key] != old_value:
                delta[key] = data[key]
        # self.config.save(payload=delta)
        # if state changed - send event
        # self.logger.debug('new user event from {}'.format(delta))
        self.logger.debug('plot now {}'.format(self.config))
        if delta:
            delta['uid'] = self.uid
            event = make_event('device', 'input', delta)
            self.q_int.put(event)
            return event
        # else do nothing - for mitigating possible loop in q_int 'device'

    def reset(self):
        """ Resetting from saved config """
        # TODO: define what the fuck is happening here
        self.config.load()
        self.logger.debug('resetting with plot\n\t{}'.format(self.config))

    def send_message(self, data):
        """ Send message to server """
        event = make_event('device', 'send', data)
        self.q_int.put(event)
        return event
