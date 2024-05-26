"""This file defines the logger used in omni's projects."""
import gzip
import os
import configparser
import shutil
import logging
import threading
import logging.handlers

def _get_formatter(log_level) -> str:
    if log_level == logging.DEBUG:
        return (
            "%(asctime)s %(levelname).1s "
            "%(threadName)s "
            '%(filename)s:%(funcName)5s:%(lineno)s | %(message)s'
        )
    else:
        return (
            "%(asctime)s %(levelname).1s "
            "%(threadName)s | %(message)s"
        )


class LogHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, file_name: str, max_bytes: int, backup_count: int, log_level):
        super().__init__(
            filename=file_name,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        self.rotator = self.rotator
        self.namer = self.namer

    @staticmethod
    def rotator(source, dest):
        with open(source, 'rb') as f_in:
            with gzip.open(dest, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)  # pyright: ignore
        os.remove(source)

    @staticmethod
    def namer(name):
        return name + ".gz"


def setup_logger(name: str, log_level=logging.INFO, stream_output=False):
    """Set the logger."""
    log_handler = LogHandler(
        file_name=f"logs/{name}.log",
        max_bytes=1000000,
        backup_count=5,
        log_level=log_level,
    )
    threading.current_thread().name = "main"
    logging.getLogger().setLevel(log_level)
    logging.getLogger().addHandler(log_handler)
    log_format: str = _get_formatter(log_level)
    log_handler.setFormatter(logging.Formatter(log_format, "%Y-%m-%dT%H:%M:%S"))
    if stream_output:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(stream_handler)


def print_version(setup_cfg_path='setup.cfg'):
    """Print version from setup_cfg_path."""
    setup_config = configparser.ConfigParser()
    setup_config.read(setup_cfg_path)
    try:
        logging.info("version %s", setup_config['metadata']['version'])
    except KeyError:
        logging.info("version not found")
