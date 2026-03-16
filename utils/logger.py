import logging
import logging.config


class LoggerManager:
    def __init__(self, logger_config: dict) -> None:
        logging.config.dictConfig(logger_config)
        self.logger = logging.getLogger("crawler")

    def debug(self, msg: object):
        self.logger.debug(msg)

    def info(self, msg: object):
        self.logger.info(msg)

    def warning(self, msg: object):
        self.logger.warning(msg)

    def error(self, msg: object, e):
        self.logger.error(msg, exc_info=e)
