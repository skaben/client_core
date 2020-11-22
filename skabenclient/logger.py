import logging
import logging.handlers
from multiprocessing import Queue
from skabenclient.helpers import make_event


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
            "lvl": record.levelno
        }
        event = make_event('device', 'send', data)
        self.queue.put(event)


def make_local_loggers(file_path: str, level: str):
    """Create local logger"""
    handlers = []
    format_str = '%(asctime)s :: <%(filename)s:%(lineno)s - %(funcName)s()>  %(levelname)s > %(message)s'
    log_format = logging.Formatter(format_str)

    fh = logging.FileHandler(filename=file_path)
    stream = logging.StreamHandler()

    for handler in (fh, stream):
        handler.setFormatter(log_format)
        handler.setLevel(level)
        handlers.append(handler)

    return handlers


def make_network_logger(queue: Queue, level: str):
    """create network logger"""
    handler = ReportHandler(queue)
    log_format = logging.Formatter("%(message)s")
    handler.setFormatter(log_format)
    handler.setLevel(level)

    return handler
