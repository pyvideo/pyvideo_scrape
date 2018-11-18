# PyVideo Scrape

## Introduction

PyVideo Scrape gets python conference videos (youtube lists) metadata and puts it into a PyVideo repository branch.

Why another PyVideo scraper?
It was my initial attempt to get data from youtube lists, worked for me. Now I cleaned it a bit and uploaded to a repo.

# Installation

~~~ bash
mkdir ~/git  # Example directory
cd  ~/git

# Get the repos (better if you have a fork of them)
git clone "git@github.com:Daniel-at-github/pyvideo_scrape.git"
git clone "git@github.com:pyvideo/data.git" pyvideo_data
~~~

# Usage

~~~ bash
cd ~/git/pyvideo_scrape

$EDITOR events.yml  # Add the conferences to scrape (see format below)
pipenv shell
pipenv update youtube-dl  # This should be good from time to time
./pyvideo_scrape.py
~~~

`events.yml` format
~~~ yml
- title: PyCon CZ 2018
  dir: pycon-cz-2018
  youtube_lists:
    - https://www.youtube.com/channel/UCRC2Vu7p4SJxhhuRdl8rQ6g/videos
  related_urls:
  - label: Conference schedule
    url: https://cz.pycon.org/2018/programme/schedule/
  language: eng
  dates:
    begin: 2018-06-01
    end: 2018-06-01
    default: 2018-06-03
  issue: 503
  minimal_download: false
  tags:
~~~

Field | description
--- | ---
title | Title field of the event
dir | Directory name of the event
youtube_list | List of youtube urls (videos and or lists)
related_urls | Url list common to all events in video
language | Videos ISO_639-3 language code
dates | Three ISO 8601 Dates between which videos were recorded (YYYY-MM-DD[Thh:mm[+hh:mm]])
dates.begin | Start date of the event
dates.end | End date of the event
dates.default | Default date to use when the videos don't have a date between begin and end
issue | Github issue solved scraping this videos
minimal_download | Download only the fields that don't need human intervention, intended for a first download that exposes the minimal data.
tags | Tags common to all events in video

The files `events_minimal_download.yml` and `events_done.yml` are manually saved to ease future data reload (especially minimal_download file).
