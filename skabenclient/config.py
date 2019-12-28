import os
import yaml
import time
import logging
from filelock import Timeout, FileLock
import multiprocessing as mp
from skabenclient.helpers import get_mac, get_ip

class Config:

    file_lock = None
    filtered_keys = list()
    root = os.path.dirname(os.path.realpath(__file__))

    def __init__(self, config_path):
        self.data = dict()
        self.config_path = config_path
        fname = os.path.basename(os.path.normpath(self.config_path)) + '.lock'
        self.flock = FileLock(os.path.join(os.path.dirname(self.config_path), fname), timeout=1)
        self.update(self.read())

    def read(self):
        """ Reads from config file """
        try:
            with self.flock:
                with open(self.config_path, 'r') as fh:
                    return yaml.load(fh, Loader=yaml.BaseLoader)
        except Timeout:
            # todo: handling second readding try
            raise
        except FileNotFoundError:
            raise
        except yaml.YAMLError:
            raise
        except Exception:
            raise
        finally:
            self.flock.release(force=True)

    def write(self):
        """ Writes to config file """
        config = self.get_values(self.__dict__)
        try:
            with self.flock:
                with open(self.config_path, 'w') as fh:
                    fh.write(yaml.dump(config))
        except Timeout:
            # todo: handling second reading try
            raise
        except Exception:
            raise
        finally:
            self.flock.release(force=True)

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


class SystemConfig(Config):

    """ Basic app configuration """

    def __init__(self, config_path=None):
        if not config_path:
            config_path = os.path.join(self.root, 'conf', 'config.yml')
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

    def logger(self, file_path=None, log_level=None):
        """ Make logger """
        if not file_path:
            file_path = 'local.log'
        if not log_level:
            log_level = logging.DEBUG
        file_path = os.path.join(self.root, file_path)

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

    def __init__(self, config_path=None):
        if not config_path:
            config_path = os.path.join(self.root, 'conf', 'running.yml')
        super().__init__(config_path)

    def load(self):
        """ Load and update configuration state from file """
        return self.update(self.read())

    def save(self, payload=None):
        """ Update current state from custom payload and save to file """
        if payload:
            self.update(payload)
        return self.write()

    def get_running(self):
        """ Get current config """
        data = self.get_values(self.data)
        if not data:
            return self.set_default()
        else:
            return data

    def set_default(self):
        """ Reset config state to defaults """
        return self.update(self.default_config)

    def get(self, key, arg=None):
        """ Get compatibility wrapper """
        return self.data.get(key, arg)

    def set(self, key, val):
        """ Set compatibility wrapper """
        return self.update({key: val})
