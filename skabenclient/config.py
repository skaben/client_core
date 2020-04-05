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

    """ Abstract config class

        Provides methods for reading and writing .yml config file with filelock
    """

    not_stored_keys = list()  # fields should not be stored in .yml
    minimal_essential_conf = dict()  # essential config

    def __init__(self, config_path):
        self.data = dict()
        self.config_path = config_path
        if not config_path:
            raise Exception(f'config path is missing for {self}')
        current = self.read()
        self.update(current)

    def read(self):
        """ Reads from config file """
        try:
            with FileLock(self.config_path):
                with open(self.config_path, 'r') as fh:
                    res = yaml.load(fh, Loader=ExtendedLoader)
                    if not res:
                        raise EOFError
        except Exception:
            raise
        return res

    def write(self, data=None, mode='w'):
        """ Writes to config file """
        if not data:
            data = self.get_values(self.data)
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
               and k not in self.not_stored_keys}
        return cfg

    def get(self, key, arg=None):
        """ Get compatibility wrapper """
        return self.data.get(key, arg)

    def set(self, key, val):
        """ Set compatibility wrapper """
        return self.update({key: val})

    def reset(self):
        """ Reset to default conf """
        self.data = self.minimal_essential_conf


class SystemConfig(Config):

    """ Basic app configuration """

    uid = None
    ip = None
    q_int = None
    q_ext = None

    def __init__(self, config_path=None, root=None):
        self.data = dict()
        self.root = root if root else os.path.abspath(os.path.dirname(__file__))
        super().__init__(config_path)
        iface = self.data.get('iface')

        if not iface:
            raise Exception('network interface missing in config')

        self.update({
            'uid': get_mac(iface),
            'ip': get_ip(iface),
            'q_int': mp.Queue(),
            'q_ext': mp.Queue(),
        })

    def write(self, data=None, mode=None):
        raise PermissionError('System config cannot be created automatically. '
                              'Seems like config file is missing or corrupted.')

    def logger(self, file_path=None, log_level=None):
        """ Make logger """
        if not file_path:
            file_path = 'local.log'
        if not log_level:
            log_level = logging.DEBUG

        if loggers.get('main'):
            logger = loggers.get('main')
        else:
            logging.basicConfig(filename=file_path, level=log_level)
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
    """

    minimal_essential_conf = {
        'dev_type': 'test'
    }

    def __init__(self, config_path):
        self.data = dict()
        self.not_stored_keys.extend(['message'])
        super().__init__(config_path)

    def write_default(self):
        """ Create config file and write default configuration to it """
        if not self.minimal_essential_conf:
            raise RuntimeError('missing minimal essential config, nothing to write')
        try:
            self.write(self.minimal_essential_conf, 'w+')
        except PermissionError as e:
            raise PermissionError(f'config file permission error: {e}')
        except Exception:
            raise
        return self.minimal_essential_conf

    def read(self):
        try:
            config = super().read()
        except (EOFError, FileNotFoundError, yaml.YAMLError):
            # file is empty or not created or corrupted, rewrite with default conf
            config = self.write_default()
        return config

    def load(self):
        """ Load and apply state from file """
        if not self.read():
            # set config to default values
            self.data = self.minimal_essential_conf
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