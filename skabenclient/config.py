import os
import yaml
import logging


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

    def logger(self, file_path=None, log_level=None):
        """ Make logger """
        if not file_path:
            file_path = 'local.log'
        if not log_level:
            log_level = logging.DEBUG
        file_path = os.path.join(self.root, file_path)
        FORMAT = '%(asctime)s :: <%(filename)s:%(lineno)s - %(funcName)s()>  %(levelname)s > %(message)s'
        logger = logging.getLogger('main')
        logger.basicConfig(filename=file_path, level=log_level, format=FORMAT)
        return logger

    def update(self, payload):
        """ Update config with payload """
        self.__dict__.update({k: v for k, v in payload if not k.startswith('_')})
