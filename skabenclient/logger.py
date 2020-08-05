import logging
from skabenclient.helpers import make_event


class ReportHandler(logging.QueueHandler):

    """ Transform log records into INFO packets """

    def __init__(self, queue):
        super().__init__(queue)

    def prepare(self, data):
        """ Prepares record as making event for internal queue """
        event = make_event('device', 'send', data)
        return event


def make_format(format):
    return logging.Formatter(format)


def make_local_loggers(file_path, level):
    """ Make logger """
    handlers = []
    logging.basicConfig(filename=file_path, level=level)
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
    log_format = make_format("%(funcName)s()>  %(levelname)s > %(message)s")
    handler.setFormatter(log_format)
    handler.setLevel(level)

    return handler


def make_logger(handlers):
    logger = logging.getLogger("main")
    for handler in handlers:
        logger.addHandler(handler)
    return logger
