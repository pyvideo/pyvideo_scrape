# PyVideo Scrape

## Introduction

PyVideo Scrape gets python conference videos (youtube lists) metadata and puts it into a PyVideo repository branch.

Why another PyVideo scraper?  
It was my initial attempt to get data from youtube lists, worked for me. Then I cleaned it a bit and uploaded to a repo.

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
- title: PyCon AU 2019
  dir: pycon-au-2019
  youtube_list:
    - https://www.youtube.com/playlist?list=PLs4CJRBY5F1LKqauI3V4E_xflt6Gow611
  related_urls:
  - label: Conference schedule
    url: https://2019.pycon-au.org/schedule
  language: eng
  dates:
    begin: 2019-08-02
    end: 2019-08-06
    default: 2019-08-02
  issue: 843
  tags:

  minimal_download: false
  overwrite:
    # all: true # takes precedence over add_new_files and existing_files_fields
    add_new_files: true
    existing_files_fields:
      - copyright_text
      - duration
      - thumbnail_url
      - videos
      - description
      - language
      # - recorded
      - related_urls
      # - speakers
      # - tags
      # - title
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
overwrite | Section needed to add new content to existing event
overwrite.all | Removes event content and downloads present videos metadata (takes precedence over add_new_files and existing_files_fields)
overwrite.add_new_files | Downloads new videos metadata (compatible with existing_files_fields)
overwrite.existing_files_fields | Updates selected fields for existing videos (compatible with add_new_files)

The files `events_minimal_download.yml` and `events_done.yml` are manually saved to ease future data reload (especially minimal_download file).

## Use cases

### New conference and little time available

Use `minimal_download: true`, download and pull request. If no more changes are added no review is needed and it's easier to publish.

### New content in a "minimal_download" conference

Reuse "minimal_download" conference configuration and add:

~~~ yaml
  # After conference data
  minimal_download: true
  overwrite:
    all: true
~~~

Old content will be erased (only automated work) and created again witth present content.

### Have time to download/review a conference

#### No existing content

Use `minimal_download: false`

#### Only automated content (previously downloaded with minimal_download)

Download using:

~~~ yaml
  # After conference data
  minimal_download: false
  overwrite:
    all: true
~~~

### New videos in a conference previously downloaded/reviewed

Download using:

~~~ yaml
  # After conference data
  minimal_download: false
  overwrite:
    add_new_files: true
~~~

### New videos in a conference partially reviewed

Suppose a conference downloaded with `minimal_download` and the fields `speakers`, `title`, `recorded` and `tags` previously reviewed and commited.
You have to download possible new files and update the rest of the fields, using:

~~~ yaml
  # After conference data
  overwrite:
    add_new_files: true
    existing_files_fields:
      - copyright_text
      - duration
      - thumbnail_url
      - videos
      - description
      - language
      - related_urls
~~~
