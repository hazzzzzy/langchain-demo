import datetime
import logging
import logging.config
import os

from utils.abs_path import abs_path

nowtime = datetime.datetime.now()
nowtime = nowtime.strftime("%Y-%m-%d_%H-%M-%S")


def logging_config():
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] [%(levelname)s] %(message)s",
                "datefmt": "%m-%d %H:%M:%S",
                # "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
            "file": {
                "class": "logging.FileHandler",
                "formatter": "default",
                "filename": abs_path(f"../log/{nowtime}.log"),
                "encoding": "utf-8",
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["console", "file"],
        },
    }


def setup_logging():
    logging.config.dictConfig(logging_config())
    logger = logging.getLogger(__name__)
    return logger


if __name__ == '__main__':
    print(os.path.abspath(__file__))