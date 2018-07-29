#!/usr/bin/env python3
"""Scrape several conferences into pyvideo repository"""

import datetime
import logging
import pathlib

from colorlog import ColoredFormatter
import yaml

LOGGER = None


def setup_logger() -> logging.Logger:
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


class Event:
    """PyVideo Event metadata"""

    def __init__(self, event_data: dict, repo_dir):
        self.repository = repo_dir
        self.title = event_data['title']
        for mandatory_field in ['title', 'dir', 'issue', 'youtube_list']:
            if mandatory_field in event_data and event_data[mandatory_field]:
                pass
            else:
                LOGGER.error('No %s data in conference %s', mandatory_field, self.title)
                raise ValueError("{} can't be null".format(mandatory_field))
        self.directory = event_data['dir']
        self.issue = event_data['issue']
        if isinstance(event_data['youtube_list'], str):
            self.youtube_lists = [event_data['youtube_list']]
        elif isinstance(event_data['youtube_list'], list):
            self.youtube_lists = event_data['youtube_list']
        else:
            raise TypeError("youtube_list must be a string or a list of strings")
        self.related_urls = event_data.get('related_urls', {})
        self.language = event_data.get('language', None)
        self.tags = event_data.get('tags', [])
        if 'dates' in event_data and event_data['dates']:
            self.know_date = True
            self.date_begin = str(event_data['dates']['begin'])
            self.date_end = str(event_data['dates'].get('end', self.date_begin))
            self.date_default = str(event_data['dates'].get('default', self.date_begin))
        else:
            self.know_date = False

def main():
    """Scrape several conferences into pyvideo repository"""

    global LOGGER
    LOGGER = setup_logger()

    time_init = datetime.datetime.now()
    LOGGER.debug('Time init: %s', time_init)

    events_file = 'events.yml'
    events_data = load_events(events_file)

    pyvideo_repo = pathlib.PosixPath(events_data['repo_dir']).expanduser().resolve()
    events = [Event(event_data, repo_dir=pyvideo_repo) for event_data in events_data['events']]
    time_end = datetime.datetime.now()
    time_delta = str(time_end - time_init)
    LOGGER.debug('Time init: %s', time_init)
    LOGGER.debug('Time end: %s', time_end)
    LOGGER.debug('Time delta: %s', time_delta)



if __name__ == '__main__':
    main()
