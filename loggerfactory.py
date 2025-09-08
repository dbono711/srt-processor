import logging


class LoggerFactory(object):
    """
    Factory class for creating logger objects with a specified log file
    and logging level. It provides a static method to initialize logger
    objects in other modules.

    Attributes:
        _LOG (logging.Logger): A class variable to store the logger object.

    Methods:
        __create_logger(log_file: str, log_level: str) -> logging.Logger:
            A private method that interacts with the python logging module.

        get_logger(log_file: str, log_level: str) -> logging.Logger:
            A static method called by other modules to initialize logger
            in their own module.
    """

    _LOG = None

    @staticmethod
    def __create_logger(log_file: str, log_level: str):
        """
        A private method that interacts with the python logging module.

        Args:
            log_file (str): Name of the log file.
            log_level (str): Logging level.

        Returns:
            logging.Logger: Logger object.
        """
        # set the logging format
        log_format = "%(asctime)s:%(levelname)s:%(message)s"

        # initialize the class variable with logger object
        LoggerFactory._LOG = logging.getLogger(log_file)
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            datefmt="%Y-%m-%d %H:%M:%S",
            filename=f"{log_file}.log",
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
        """
        A static method called by other modules to initialize logger
        in their own module.

        Args:
            log_file (str): Name of the log file.
            log_level (str): Logging level.

        Returns:
            logging.Logger: Logger object.
        """
        return LoggerFactory.__create_logger(log_file, log_level)
