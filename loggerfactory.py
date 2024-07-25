import logging


class LoggerFactory(object):
    """Docstring missing."""

    _LOG = None

    @staticmethod
    def __create_logger(log_file: str, log_level: str):
        """A private method that interacts with the python
        logging module

        Args:
            log_file (str): Name of the log file
            log_level (str): Logging level
        """
        # set the logging format
        log_format = "%(asctime)s:%(levelname)s:%(message)s"

        # initialize the class variable with logger object
        LoggerFactory._LOG = logging.getLogger(log_file)
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            datefmt="%Y-%m-%d %H:%M:%S",
            filename=f"logs/{log_file}.log",
        )

        # set the logging level based on the user selection
        if log_level == "INFO":
            LoggerFactory._LOG.setLevel(logging.INFO)
        elif log_level == "ERROR":
            LoggerFactory._LOG.setLevel(logging.ERROR)
        elif log_level == "DEBUG":
            LoggerFactory._LOG.setLevel(logging.DEBUG)
        return LoggerFactory._LOG

    @staticmethod
    def get_logger(log_file: str, log_level: str):
        """A static method called by other modules to initialize
        logger in their own module

        Args:
            log_file (str): Name of the log file
            log_level (str): Logging level
        """
        return LoggerFactory.__create_logger(log_file, log_level)
