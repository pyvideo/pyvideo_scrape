#!/usr/bin/env python3
"""Scrape several conferences into pyvideo repository"""

import copy
import datetime
import json
import os
import pathlib
import re
import sys

import sh
import slugify
import yaml
import youtube_dl

from loguru import logger

JSON_FORMAT_KWARGS = {
    'indent': 2,
    'separators': (',', ': '),
    'sort_keys': True,
}


def load_events(fich):
    """Loads events data yaml file"""
    with fich.open() as fd_conf:
        conf = yaml.safe_load(fd_conf)
    return conf


def save_file(path, text):
    """Create a file in `path` with content `text`"""
    with path.open(mode='w') as f_stream:
        f_stream.write(text)


def youtube_dl_version():
    """Returns the actual version of youtube-dl"""
    import pkg_resources

    return pkg_resources.get_distribution("youtube-dl").version


class Event:
    """PyVideo Event metadata"""

    def __init__(self, event_data: dict, repository_path):
        self.videos = []
        self.repository_path = repository_path

        self.branch = event_data['dir']
        self.event_dir = self.repository_path / event_data['dir']
        self.video_dir = self.event_dir / 'videos'

        self.title = event_data['title']
        for mandatory_field in ['title', 'dir', 'issue', 'youtube_list']:
            if mandatory_field in event_data and event_data[mandatory_field]:
                pass
            else:
                logger.error('No {} data in conference {}', mandatory_field,
                             self.title)
                raise ValueError("{} can't be null".format(mandatory_field))
        self.issue = event_data['issue']

        if isinstance(event_data['youtube_list'], str):
            self.youtube_lists = [event_data['youtube_list']]
        elif isinstance(event_data['youtube_list'], list):
            self.youtube_lists = event_data['youtube_list']
        else:
            raise TypeError(
                "youtube_list must be a string or a list of strings")

        self.related_urls = event_data.get('related_urls', [])
        self.language = event_data.get('language', None)
        self.tags = event_data.get('tags', [])
        if not self.tags:
            self.tags = []

        if 'dates' in event_data and event_data['dates']:
            self.know_date = True
            self.date_begin = event_data['dates']['begin']
            self.date_end = event_data['dates'].get('end', self.date_begin)
            self.date_default = event_data['dates'].get(
                'default', self.date_begin)
        else:
            self.know_date = False
        self.minimal_download = event_data.get('minimal_download', False)
        if self.minimal_download:
            self.branch = "{}--minimal-download".format(self.branch)

    def create_branch(self):
        """Create a new branch in pyvideo repository to add a new event"""
        os.chdir(str(self.repository_path))
        sh.git.checkout('master')
        sh.git.checkout('-b', self.branch)
        logger.debug('Branch {} created', self.branch)

    def create_dirs(self):
        """Create new directories and conference file in pyvideo repository to add a new event"""
        for new_directory in [self.event_dir, self.event_dir / 'videos']:
            # assert not new_directory.exists() , 'Dir {} already exists'.format(str(new_directory))
            new_directory.mkdir(exist_ok=False)
            logger.debug('Dir {} created', new_directory)

    def create_category(self):  # , conf_dir, title):
        """Create category.json for the conference"""
        category_file_path = self.event_dir / 'category.json'
        category_data = {
            'title': self.title,
        }
        category_data_text = json.dumps(category_data, **
                                        JSON_FORMAT_KWARGS) + '\n'
        save_file(category_file_path, category_data_text)
        logger.debug('File {} created', category_file_path)

    def download_video_data(self):
        """Download youtube metadata corresponding to this event youtube lists"""

        def scrape_url(url):
            """Scrape the video list, youtube_dl does all the heavy lifting"""
            ydl_opts = {
                "ignoreerrors": True,  # Skip private and unavaliable videos
            }

            ydl = youtube_dl.YoutubeDL(ydl_opts)

            with ydl:
                result_ydl = ydl.extract_info(
                    url,
                    download=False  # No download needed, only the info
                )

            logger.debug('Url scraped {}', url)
            if 'entries' in result_ydl:
                # It's a playlist or a list of videos
                return result_ydl['entries']
            else:
                # Just a video
                return [result_ydl]

        youtube_list = sum((scrape_url(url) for url in self.youtube_lists), [])
        for youtube_video_data in youtube_list:
            if youtube_video_data:  # Valid video
                self.videos.append(
                    Video(video_data=youtube_video_data, event=self))
            else:
                logger.warning('Null youtube video')

    def save_video_data(self):
        """Save all event videos in PyVideo format"""
        for video in self.videos:
            video.save()

    def create_commit(self):
        """Create a new commit in pyvideo repository with the new event data"""
        os.chdir(str(self.repository_path))
        sh.git.checkout(self.branch)
        sh.git.add(self.event_dir)
        if self.minimal_download:
            message = 'Minimal download: {}\n\nminimal download executed for #{}'.format(
                self.title, self.issue)
            sh.git.commit('-m', message)
            sh.git.push('--set-upstream', 'origin', self.branch)
            # ~ sh.git.push('--set-upstream', '--force', 'origin', self.branch)
            sh.git.checkout('master')
        else:
            message = 'Scraped {}\n\nFixes #{}'.format(self.branch, self.issue)
            sh.git.commit('-m', message)
            sh.git.checkout('master')
        logger.debug('Conference {} commited', self.branch)


class Video:
    """PyVideo Video metadata"""

    @staticmethod
    def __calculate_title(video_data):
        """Calculate title from youtube fields"""
        title = 'Unknown'
        if 'fulltitle' in video_data.keys():
            title = video_data['fulltitle']
        elif 'title' in video_data.keys():
            title = video_data['title']
        elif '_filename' in video_data.keys():
            title = video_data['_filename']
        return title

    def __calculate_slug(self):
        """Calculate slug from title"""

        return slugify.slugify(self.title)

    def __calculate_date_recorded(self, upload_date_str):
        """Calculate record date from youtube field and event dates"""

        upload_date = datetime.date(
            int(upload_date_str[0:4]),
            int(upload_date_str[4:6]), int(upload_date_str[6:8]))
        if self.event.know_date:
            if not (self.event.date_begin <= upload_date <=
                    self.event.date_end):
                return self.event.date_default.isoformat()

        return upload_date.isoformat()

    def __init__(self, video_data, event):
        self.event = event

        self.title = self.__calculate_title(video_data)
        self.filename = self.__calculate_slug()
        self.speakers = ['TODO']  # Needs human intervention later
        # youtube_id = video_data['display_id']
        # self.thumbnail_url = 'https://i.ytimg.com/vi/{}/maxresdefault.jpg'.format(youtube_id)
        self.thumbnail_url = video_data['thumbnail']
        self.videos = [{'type': 'youtube', 'url': video_data['webpage_url']}]
        self.recorded = self.__calculate_date_recorded(
            video_data['upload_date'])

        # optional values
        self.copyright_text = video_data['license']
        self.duration = video_data['duration']  # In seconds
        self.language = video_data['formats'][0].get('language',
                                                     event.language)
        if not self.language:
            self.language = event.language
        self.related_urls = copy.deepcopy(event.related_urls)

        if event.minimal_download:
            self.speakers = []
            self.tags = event.tags
            self.description = ''
        else:
            self.tags = sorted(set(video_data['tags']).union(set(event.tags)))
            self.description = video_data['description']
            description_urls = list(
                set(
                    re.findall(r'http[s]?://[^ \\\n\t()[\]"`´\']+', video_data[
                        'description'])))
            for url in description_urls:
                self.related_urls.append({'label': url, 'url': url})

    def save(self):
        """"Save to disk"""
        path = self.event.video_dir / '{}.json'.format(self.filename)
        if path.exists():
            duplicate_num = 1
            new_path = path
            while new_path.exists():
                duplicate_num += 1
                new_path = path.parent / (
                    path.stem + '-{}{}'.format(duplicate_num, path.suffix))
                logger.debug('Duplicate, renaming to {}', path)
            path = new_path

        data = {
            'title': self.title,
            'speakers': self.speakers,
            'thumbnail_url': self.thumbnail_url,
            'videos': self.videos,
            'recorded': self.recorded,
            'copyright_text': self.copyright_text,
            'duration': self.duration,
            'language': self.language,
            'related_urls': self.related_urls,
        }
        if 'tags' in self.__dict__:
            data['tags'] = self.tags
        if 'description' in self.__dict__:
            data['description'] = self.description

        data_text = json.dumps(data, **JSON_FORMAT_KWARGS) + '\n'
        save_file(path, data_text)
        logger.debug('File {} created', path)


@logger.catch
def main():
    """Scrape several conferences into pyvideo repository"""

    logger.add(
        sys.stderr,
        format="{time} {level} {message}",
        filter="my_module",
        level="DEBUG")

    time_init = datetime.datetime.now()
    logger.debug('Time init: {}', time_init)
    logger.debug('youtube-dl version: {} ', youtube_dl_version())

    cwd = pathlib.Path.cwd()

    events_file = cwd / 'events.yml'
    events_data = load_events(events_file)

    pyvideo_repo = pathlib.PosixPath(
        events_data['repo_dir']).expanduser().resolve()
    events = [
        Event(event_data, repository_path=pyvideo_repo)
        for event_data in events_data['events']
    ]
    for event in events:
        try:
            event.create_branch()
            event.create_dirs()
            event.create_category()
        except (sh.ErrorReturnCode_128, FileExistsError) as exc:
            logger.warning('Event {} skipped', event.branch)
            logger.debug(exc.args[0])
            continue
        event.download_video_data()
        event.save_video_data()
        event.create_commit()

    time_end = datetime.datetime.now()
    time_delta = str(time_end - time_init)
    logger.debug('Time init: {}', time_init)
    logger.debug('Time end: {}', time_end)
    logger.debug('Time delta: {}', time_delta)
    # TODO: mypy


if __name__ == '__main__':
    main()
