import logging
import logging.config
import logging.handlers
import os
from multiprocessing import Queue

from skabenclient.helpers import make_event


def get_baseconf(root: str, debug: bool = False) -> dict:
    logsize = 5120000
    fmt = '%(asctime)s :: %(processName)-10s :: <%(filename)s:%(lineno)s - %(funcName)s()>  %(levelname)s > %(message)s'
    min_log_level = 'DEBUG' if debug else 'INFO'

    return {
        'version': 1,
        'formatters': {
            'short': {
                'class': 'logging.Formatter',
                'format': '%(asctime)s :: %(processName)-10s :: %(levelname)s > %(message)s',
            },
            'detailed': {
                'class': 'logging.Formatter',
                'format': fmt
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': min_log_level,
                'formatter': 'short'
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'maxBytes': logsize,
                'backupCount': 5,
                'filename': os.path.join(root, 'messages.log'),
                'formatter': 'detailed',
            },
            'errors': {
                'class': 'logging.handlers.RotatingFileHandler',
                'maxBytes': logsize,
                'backupCount': 3,
                'filename': os.path.join(root, 'errors.log'),
                'level': 'ERROR',
                'formatter': 'detailed',
            },
        },
        'root': {
            'level': min_log_level,
            'handlers': ['console', 'file', 'errors']
        },
    }


class ReportHandler(logging.handlers.QueueHandler):
    """Custom INFO log sender, transform records into INFO packets"""

    def __init__(self, queue):
        super().__init__(queue)
        self.queue = queue

    def prepares(self, record):
        return record

    def enqueue(self, record):
        data = {
            "msg": record.msg,
            "lvl": record.levelname
        }
        event = make_event('device', 'send', data)
        self.queue.put(event)


class CoreLogger:

    def __init__(self,
                 root: str,
                 logging_queue: Queue,
                 internal_queue: Queue,
                 debug: bool):
        self.loggers = []
        self.root_logger = None
        self.logging_queue = logging_queue
        self.internal_queue = internal_queue
        self.config = get_baseconf(root, debug)

    def make_root_logger(self) -> logging.Logger:
        """Make root logger"""
        if self.root_logger:
            return self.root_logger
        logging.config.dictConfig(self.config)
        self.root_logger = logging.root
        return logging.root

    def add_external_handler(self, logger: logging.Logger, level: int = None) -> logging.Logger:
        """Add handler which converts log records to INFO messages and passes them into internal queue"""
        if not level or not isinstance(level, int):
            level = logging.ERROR
        handler = ReportHandler(self.internal_queue)
        log_format = logging.Formatter("%(message)s")
        handler.setFormatter(log_format)
        handler.setLevel(level)
        logger.addHandler(handler)
        return logger

    def make_logger(self, name: str = None, level: int = logging.DEBUG, ext_level: int = None) -> logging.Logger:
        """Make logger from any process"""
        if not name:
            name = f'{__name__}-{os.getpid()}'
        instance = logging.getLogger(name)
        if name in self.loggers:
            return instance
        self.loggers.append(name)
        handler = logging.handlers.QueueHandler(self.logging_queue)  # Just the one handler needed
        instance.addHandler(handler)
        instance.setLevel(level)
        if ext_level:
            instance = self.add_external_handler(instance, ext_level)
        instance.propagate = False  # no propagation for logger with QueueHandler
        return instance
