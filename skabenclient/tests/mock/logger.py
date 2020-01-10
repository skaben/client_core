class MockLogger:

    """ Super stupid mock logger """

    def debug(self, msg=None):
        return msg

    def error(self, msg=None):
        return msg

    def info(self, msg=None):
        return msg

    def warning(self, msg=None):
        return msg

    def critical(self, msg=None):
        return msg