from skabenclient.config import DeviceConfig, SystemConfig
from skabenclient.helpers import make_event


class BaseDevice:

    """ Abstract device handler class.

        Handling user input and end device state.
        All persistent storage operations and server interactions is performed by contexts
    """

    config_class = DeviceConfig
    timers = {}

    def __init__(self, app_config: SystemConfig, device_config: DeviceConfig):
        # assign system config
        self.system = app_config
        self.q_int = app_config.get('q_int')
        self.uid = app_config.get('uid')
        self.logger = app_config.logger()
        # assign device ingame config
        self.config = device_config
        self.config.load()  # load and update current running conf

    def run(self):
        """start application device module"""
        self.logger.info('application starting')
        self.logger.debug(f'{self} starting with device config: \n {self.config}')
        reload_event = make_event('device', 'reload')
        self.q_int.put(reload_event)

    def stop(self):
        """stop application device module"""
        self.logger.info('device is stopping...')
        self.logger.debug(f"stopping device {self}")
        end_event = make_event("exit")
        self.q_int.put(end_event)

    def state_update(self, data: dict):
        """Update device configuration from user actions

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
        """Re-read and apply device saved state"""
        return self.config.load()

    def send_message(self, data: dict):
        """Send message to server"""
        event = make_event('device', 'info', data)
        self.q_int.put(event)
        return event

    def new_timer(self, start: int, count: int, name: str) -> str:
        """Assign timer with given start time, duration and name"""
        if count > 0:
            self.timers.update({name: int(round(start + count))})
            self.logger.debug(f"timer set at {start} with name {name} to {count}s")
            return self.timers[name]
        else:
            self.logger.error(f'timer {name} cannot be set to 0')

    def check_timer(self, name: str, now: int) -> bool:
        """Check if named timer has already expired"""
        timer = self.timers.get(name)
        if timer and timer <= now:
            return timer

    @property
    def state(self):
        return self.config.data

    def save(self, data=None):
        return self.config.save(data)

    def load(self):
        return self.config.load()

    def __str__(self):
        return f"Basic Device <{self.system}>"
