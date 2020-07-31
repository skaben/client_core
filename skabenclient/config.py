import os
import yaml
import logging
import multiprocessing as mp
from skabenclient.helpers import get_mac, get_ip, FileLock, make_logger
from skabenclient.loaders import get_yaml_loader

loggers = {}
ExtendedLoader = get_yaml_loader()


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

    def _yaml_load(self, source):
        """ Loads yaml with correct Loader """
        result = yaml.load(source, Loader=ExtendedLoader)
        if not result:
            raise EOFError(f"{source} cannot be loaded")
        return result

    def read(self):
        """ Reads from config file """
        try:
            with FileLock(self.config_path):
                with open(self.config_path, 'r') as fh:
                    return self._yaml_load(fh)
        except Exception:
            raise

    def write(self, data=None, mode='w'):
        """ Writes to config file """
        if not data:
            data = self.data
        try:
            data = self._filter(data)
            with FileLock(self.config_path):
                with open(self.config_path, mode) as fh:
                    dump = yaml.dump(self._filter(data), default_flow_style=False)
                    fh.write(dump)
        except Exception:
            raise

    def get(self, key, arg=None):
        """ Get compatibility wrapper """
        return self.data.get(key, arg)

    def set(self, key, val):
        """ Set compatibility wrapper """
        return self.update({key: val})

    def update(self, payload):
        """ Updates local namespace from payload with basic filtering """
        self.data.update(self._filter(payload))
        return self.data

    def _filter(self, payload):
        """ Filter keys starting with underscore and by filtered keys list """
        cfg = {k: v for k, v in payload.items()
               if not k.startswith('_') and k not in self.not_stored_keys}
        return cfg


class SystemConfig(Config):

    """ Basic skaben read-only configuration """

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

        topic = self.data.get('topic')
        uid = get_mac(iface)

        # set PUB/SUB topics
        _publish = f'ask/{topic}'
        # 'all' reserved for broadcast messages
        _subscribe = [f"{topic}/all/#", f"{topic}/{uid}/#"]

        # update config with session values, this will not be saved to file
        self.update({
            'uid': uid,
            'ip': get_ip(iface),
            'q_int': mp.Queue(),
            'q_ext': mp.Queue(),
            'pub': _publish,
            'sub': _subscribe,
        })

    def logger(self, name='main', file_path='local.log', log_level=logging.DEBUG):
        logger = loggers.get(name)
        if not logger:
            logger = make_logger(file_path, log_level)
            loggers.update({name: logger})
        return logger

    def write(self, data=None, mode=None):
        raise PermissionError('System config cannot be created automatically. '
                              'Seems like config file is missing or corrupted.')


class DeviceConfig(Config):

    """
        Device configuration, read-write
    """

    minimal_essential_conf = {}

    def __init__(self, config_path):
        self.data = dict()
        self.not_stored_keys.extend(['message'])
        super().__init__(config_path)

    def write_default(self):
        """ Create config file and write default configuration to it """
        if not self.minimal_essential_conf:
            raise RuntimeError('minimal essential conf values is missing, '
                               'config file cannot be reset to defaults')
        try:
            self.data = self.minimal_essential_conf
            self.write()
            return self.data
        except PermissionError as e:
            raise PermissionError(f'config file write permission error: {e}')
        except Exception:
            raise

    def read(self):
        try:
            config = super().read()
            # make a consistency check
            if not set(self.minimal_essential_conf.keys()).issubset(set(config.keys())):
                # check failed, essential keys missing
                raise AttributeError
        except (EOFError, FileNotFoundError, yaml.YAMLError, AttributeError):
            # file is empty or not created or corrupted, rewrite with default conf
            config = self.write_default()
        except Exception:
            raise
        return config

    def load(self):
        """ Load and apply state from file """
        try:
            current_conf = self.read()
            if not current_conf:
                raise Exception('config inconsistency')
            for k in self.minimal_essential_conf:
                if k not in current_conf:
                    raise Exception('config inconsistency')
            return self.update(self.read())
        except Exception:
            return self.write_default()

    def save(self, payload=None):
        """ Apply and save persistent state """
        if payload:
            self.update(payload)
        return self.write(payload)

    def current(self):
        """ Get current config """
        return self.data
