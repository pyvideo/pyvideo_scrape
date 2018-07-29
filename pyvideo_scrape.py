#!/usr/bin/env python3
"""Scrape several conferences into pyvideo repository"""

import datetime
import logging
import pathlib

from colorlog import ColoredFormatter
import yaml

LOGGER = None


def setup_logger():
    """Return a logger with a default ColoredFormatter."""
    # From https://github.com/borntyping/python-colorlog/blob/master/doc/
    #   example.py
    formatter = ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red',
        })

    logger = logging.getLogger('pyvideo-scrape')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    return logger


def load_events(fich):
    """Loads events data yaml file"""
    with open(fich, 'r') as fd_conf:
        conf = yaml.safe_load(fd_conf)
        return conf


def main():
    """Scrape several conferences into pyvideo repository"""

    global LOGGER
    LOGGER = setup_logger()

    time_init = datetime.datetime.now()
    LOGGER.debug('Time init: %s', time_init)

    events_file = 'events.yml'
    events_data = load_events(events_file)

    time_end = datetime.datetime.now()
    time_delta = str(time_end - time_init)
    LOGGER.debug('Time init: %s', time_init)
    LOGGER.debug('Time end: %s', time_end)
    LOGGER.debug('Time delta: %s', time_delta)



if __name__ == '__main__':
    main()
