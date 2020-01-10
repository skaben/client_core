import os
import yaml
import time
import logging
import multiprocessing as mp
from skabenclient.helpers import get_mac, get_ip
from skabenclient.loaders import get_yaml_loader

ExtendedLoader = get_yaml_loader()


class FileLock:

    locked = None

    def __init__(self, file_to_lock, timeout=1):
        self.timeout = timeout
        self.lock_path = os.path.abspath(file_to_lock) + '.lock'

    def acquire(self):
        """ """
        idx = 0
        while not self.locked:
            try:
                time.sleep(.1)
                with open(self.lock_path, 'w+') as fl:
                    content = fl.read().strip()
                    print(content)
                    if content != '1':
                        fl.write('1')
                        self.locked = True
                        return self.locked
                idx += .1
                if idx >= self.timeout:
                    raise Exception('failed to acquire file lock by timeout')
            except Exception:
                raise

    def release(self):
        """ Release file lock """
        with open(self.lock_path, 'w') as fl:
            fl.write('0')
        self.locked = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *err):
        self.release()
        return


class Config:

    filtered_keys = list()
    root = os.path.dirname(os.path.realpath(__file__))

    def __init__(self, config_path):
        self.data = dict()
        self.config_path = config_path
        self.update(self.read())

    def read(self):
        """ Reads from config file """
        try:
            with FileLock(self.config_path):
                with open(self.config_path, 'r') as fh:
                    return yaml.load(fh, Loader=ExtendedLoader)
        except FileNotFoundError:
            raise
        except yaml.YAMLError:
            raise
        except Exception:
            raise

    def write(self):
        """ Writes to config file """
        config = self.get_values(self.data)
        try:
            with FileLock(self.config_path):
                with open(self.config_path, 'w') as fh:
                    fh.write(yaml.dump(config))
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


class SystemConfig(Config):

    """ Basic app configuration """

    def __init__(self, config_path=None):
        self.data = dict()
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
        self.data = dict()
        if not config_path:
            config_path = os.path.join(self.root, 'conf', 'running.yml')
        super().__init__(config_path)

    def load(self):
        """ Load and apply state from file """
        return self.update(self.read())

    def save(self, payload=None):
        """ Apply and save persistent state """
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
        """ Reset config state to defaults without saving to file """
        self.data = self.default_config
