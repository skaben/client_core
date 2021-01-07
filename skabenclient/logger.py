import os
import logging
import logging.handlers
import logging.config

from multiprocessing import Queue
from skabenclient.helpers import make_event


def get_baseconf(name: str) -> dict:
    fmt = '%(asctime)s :: %(processName)-10s :: <%(filename)s:%(lineno)s - %(funcName)s()>  %(levelname)s > %(message)s'

    return {
        'version': 1,
        'formatters': {
            'detailed': {
                'class': 'logging.Formatter',
                'format': fmt
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
            },
            'file': {
                'class': 'logging.FileHandler',
                'filename': f'{name}.log',
                'mode': 'w',
                'formatter': 'detailed',
            },
            'errors': {
                'class': 'logging.FileHandler',
                'filename': f'{name}-errors.log',
                'mode': 'w',
                'level': 'ERROR',
                'formatter': 'detailed',
            },
        },
        'root': {
            'level': 'DEBUG',
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

    def __init__(self, name: str, internal_queue: Queue, logging_queue: Queue):
        self.loggers = []
        self.root_logger = None
        self.name = name or 'device'
        self.logging_queue = logging_queue
        self.internal_queue = internal_queue
        self.config = get_baseconf(self.name)

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
            name = str(os.getpid())
        instance = logging.getLogger(name)
        if name in self.loggers:
            return instance
        self.loggers.append(name)
        handler = logging.handlers.QueueHandler(self.logging_queue)  # Just the one handler needed
        instance.addHandler(handler)
        instance.setLevel(level)
        if ext_level:
            instance = self.add_external_handler(instance, ext_level)
        return instance
