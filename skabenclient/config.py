import os
import yaml
import logging
import multiprocessing as mp
from skabenclient.helpers import get_mac, get_ip


class Config:

    def __init__(self, conf_path=None):

        self.root = os.path.dirname(os.path.realpath(__file__))

        if not conf_path:
            conf_path = os.path.join('conf', 'config.yml')

        with open(os.path.join(os.getcwd(), conf_path)) as f:
            try:
                yaml_conf = yaml.load(f, Loader=yaml.BaseLoader)
                self.update(yaml_conf)
            except Exception:
                raise

        self.update({
            'uid': get_mac(self.iface),
            'ip': get_ip(self.iface),
            'q_int': mp.Queue(),
            'q_ext': mp.Queue()
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

    def update(self, payload):
        """ Update config with payload """
        new_values = {k: v for k, v in payload.items() if not k.startswith('_')}
        self.__dict__.update(**new_values)
