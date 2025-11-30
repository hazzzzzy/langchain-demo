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
    # 1. 屏蔽 httpx 和 httpcore 的 INFO 日志 (这是最主要的来源)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # 2. (可选) 如果还需要屏蔽 openai 或 langchain 内部的繁杂日志
    # logging.getLogger("openai").setLevel(logging.WARNING)
    # logging.getLogger("langchain").setLevel(logging.WARNING)
    # logging.getLogger("chroma").setLevel(logging.WARNING)
    logger = logging.getLogger(__name__)
    return logger


if __name__ == '__main__':
    print(os.path.abspath(__file__))