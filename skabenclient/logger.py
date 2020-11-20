import logging
import logging.handlers
from skabenclient.helpers import make_event


class ReportHandler(logging.handlers.QueueHandler):

    """ Transform log records into INFO packets """

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


def make_format(format):
    return logging.Formatter(format)


def make_local_loggers(file_path, level):
    """ Make logger """
    handlers = []
    log_format = make_format('%(asctime)s :: <%(filename)s:%(lineno)s - %(funcName)s()>  %(levelname)s > %(message)s')

    # set handlers
    fh = logging.FileHandler(filename=file_path)
    stream = logging.StreamHandler()

    for handler in (fh, stream):
        handler.setFormatter(log_format)
        handler.setLevel(level)
        handlers.append(handler)

    return handlers


def make_network_logger(queue, level):
    handler = ReportHandler(queue)
    log_format = make_format("%(message)s")
    handler.setFormatter(log_format)
    handler.setLevel(level)

    return handler
