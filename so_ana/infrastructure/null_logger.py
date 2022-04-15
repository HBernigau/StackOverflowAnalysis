import logging


def get_null_logger(logger_name: str = 'default null logger') -> logging.Logger:
    """
    returns a standard null logger

    :param logger_name:
    :return:
    """
    fb_null_logger = logging.getLogger(logger_name)
    fb_null_logger.setLevel(logging.DEBUG)
    fb_null_logger.addHandler(logging.NullHandler())
    return fb_null_logger
