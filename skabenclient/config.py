import os
import yaml
import logging
import multiprocessing as mp
from skabenclient.helpers import get_mac, get_ip, FileLock
from skabenclient.loaders import get_yaml_loader

ExtendedLoader = get_yaml_loader()
loggers = {}

# TODO: config path generation, default config writing


class Config:

    filtered_keys = list()
    default_config = dict()
    root = os.getcwd()

    def __init__(self, config_path):
        self.data = dict()
        self.config_path = config_path
        if not config_path:
            raise Exception(f'config path is missing for {self}')
        self.update(self.read())

    def read(self):
        """ Reads from config file """
        try:
            with FileLock(self.config_path):
                with open(self.config_path, 'r') as fh:
                    return yaml.load(fh, Loader=ExtendedLoader)
        except FileNotFoundError:
            self.write(self.default_config, 'w+')
            return self.default_config
        except yaml.YAMLError:
            raise
        except Exception:
            raise

    def write(self, data=None, mode='w'):
        """ Writes to config file """
        if not data:
            data = self.data
        try:
            with FileLock(self.config_path):
                with open(self.config_path, mode) as fh:
                    fh.write(yaml.dump(self.get_values(data)))
        except Exception:
            raise

    def update(self, payload):
        """ Updates local namespace from payload with basic filtering """
        self.data.update(self.get_values(payload))
        return self.data

    def get_values(self, payload):
        """ Filter keys starting with underscore and by filtered keys list """
        cfg = {k: v for k, v in payload.items()
               if not k.startswith('_')
               and k not in self.filtered_keys}
        return cfg

    def get(self, key, arg=None):
        """ Get compatibility wrapper """
        return self.data.get(key, arg)

    def set(self, key, val):
        """ Set compatibility wrapper """
        return self.update({key: val})

    def reset(self):
        """ Reset to default conf """
        self.data = self.default_config

#    @property
#    def read_only(self):
#        """ Config data read-only """
#        # TODO: make data frozen
#        pass


class SystemConfig(Config):

    """ Basic app configuration """

    def __init__(self, config_path=None):
        self.data = dict()
        super().__init__(config_path)
        iface = self.data.get('iface')

        if not iface:
            raise Exception('network interface missing in config')

        self.update({
            'uid': get_mac(iface),
            'ip': get_ip(iface),
            'q_int': mp.Queue(),
            'q_ext': mp.Queue(),
            'device_conf': os.path.join(self.root, "conf", "device.yml")
        })

    def logger(self, file_path=None, log_level=None):
        """ Make logger """
        if not file_path:
            file_path = 'local.log'
        if not log_level:
            log_level = logging.DEBUG
        file_path = os.path.join(self.root, file_path)

        if loggers.get('main'):
            logger = loggers.get('main')
        else:
            logger = logging.getLogger('main')
            FORMAT = '%(asctime)s :: <%(filename)s:%(lineno)s - %(funcName)s()>  %(levelname)s > %(message)s'
            log_format = logging.Formatter(FORMAT)
            # set handlers
            fh = logging.FileHandler(filename=file_path)
            stream = logging.StreamHandler()
            # assign
            for handler in (fh, stream):
                handler.setFormatter(log_format)
                handler.setLevel(log_level)
                logger.addHandler(handler)
            logger.setLevel(log_level)
            loggers.update({'main': logger})
        return logger


class DeviceConfig(Config):

    """
        Local data persistent storage operations
        ! use only in device handlers !
    """

    default_config = {
        'dev_type': 'not_used',
    }

    filtered_keys = ['message']  # this keys will not be stored in config file

    def __init__(self, config_path):
        self.data = dict()
        super().__init__(config_path)

    def load(self):
        """ Load and apply state from file """
        if not self.read():
            # set config to default values
            self.data = self.default_config
            self.write()
            return self.data
        else:
            return self.update(self.read())

    def save(self, payload=None):
        """ Apply and save persistent state """
        if payload:
            self.update(payload)
        return self.write(self.data)

    def get_current(self):
        """ Get current config """
        return self.data
