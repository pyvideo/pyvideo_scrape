#!/usr/bin/env python3
"""Scrape several conferences into pyvideo repository"""

import copy
import datetime
import json
import pathlib
import re
import sys

from git import Repo, GitCommandError
import slugify
import yaml
import yt_dlp as youtube_dl

from loguru import logger

JSON_FORMAT_KWARGS = {
    'indent': 2,
    'separators': (',', ': '),
    'sort_keys': True,
}


def load_events(fich):
    """Loads events data yaml file"""
    with fich.open() as fd_conf:
        yaml_text = fd_conf.read()
    conf = yaml.safe_load(yaml_text)
    return yaml_text, conf


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
        self.youtube_videos = []
        self.file_videos = []
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

        self.overwrite, self.add_new_files, self.wipe = False, False, False
        self.overwrite_fields = []
        if 'overwrite' in event_data and event_data['overwrite']:
            overwrite = event_data['overwrite']
            self.overwrite = True
            if 'all' in overwrite and overwrite['all']:
                self.wipe = True
            else:
                if 'add_new_files' in overwrite and overwrite['add_new_files']:
                    self.add_new_files = True
                if ('existing_files_fields' in overwrite
                        and overwrite['existing_files_fields']):
                    self.overwrite_fields = overwrite['existing_files_fields']

    def create_branch(self):
        """Create a new branch in pyvideo repository to add a new event"""
        repo = Repo(str(self.repository_path))
        repo.git.checkout('main')
        new_branch = repo.create_head(self.branch)
        new_branch.checkout()
        logger.debug('Branch {} created', self.branch)

    def create_dirs(self):
        """Create new directories and conference file in pyvideo repository to
            add a new event"""
        for new_directory in [self.event_dir, self.event_dir / 'videos']:
            new_directory.mkdir(exist_ok=self.overwrite)
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
        """Download youtube metadata corresponding to this event youtube
            lists"""

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
            # Just a video
            return [result_ydl]

        youtube_list = sum((scrape_url(url) for url in self.youtube_lists), [])
        for youtube_video_data in youtube_list:
            if youtube_video_data:  # Valid video
                self.youtube_videos.append(
                    Video.from_youtube(
                        video_data=youtube_video_data, event=self))
            else:
                logger.warning('Null youtube video')

    def load_video_data(self):
        """Load video data form existing event video files"""
        self.file_videos = [
            Video.from_file(path, self)
            for path in self.video_dir.glob('*.json')
        ]

    def merge_video_data(self):
        """Merge old video data when configured so"""
        if self.overwrite:
            if self.wipe:
                self.videos = self.youtube_videos
            elif self.add_new_files or self.overwrite_fields:
                old_videos = {
                    video.filename: video
                    for video in self.file_videos
                }
                old_videos_url = {
                    video.metadata['videos'][0]['url']: video
                    for video in self.file_videos
                }
                new_videos = {}
                for video in self.youtube_videos:
                    new_video_url = video.metadata['videos'][0]['url']
                    if new_video_url in old_videos_url:
                        new_video_filename = old_videos_url[new_video_url].filename
                    else:
                        new_video_filename = video.filename
                    new_videos[new_video_filename] = video

                if self.overwrite_fields:
                    forgotten = set(old_videos) - set(new_videos)
                    for name in forgotten:
                        logger.warning('Missing video: {} {}',
                            old_videos[name].filename,
                            old_videos[name].metadata['videos'][0]['url'],
                            )

                    changes = set(new_videos).intersection(set(old_videos))
                    for path in changes:
                        merged_video = old_videos[path].merge(
                            new_videos[path], self.overwrite_fields)
                        self.videos.append(merged_video)
                else:
                    self.videos = self.file_videos
                if self.add_new_files:
                    adds = set(new_videos) - set(old_videos)
                    self.videos.extend([new_videos[path] for path in adds])
        else:  # not self.overwrite
            self.videos = self.youtube_videos

    def save_video_data(self):
        """Save all event videos in PyVideo format"""
        if self.overwrite:
            # Erase old event videos
            for path in self.video_dir.glob('*.json'):
                path.unlink()
        for video in self.videos:
            video.save()

    def create_commit(self, event_data_yaml):
        """Create a new commit in pyvideo repository with the new event data"""
        repo = Repo(str(self.repository_path))
        repo.git.checkout(self.branch)
        repo.git.add(self.event_dir)
        message_body = (
            '\n\nEvent config:\n~~~yaml\n{}\n~~~\n'.format(event_data_yaml)
            + '\nScraped with [pyvideo_scrape]'
            + '(https://github.com/pyvideo/pyvideo_scrape)')
        if self.minimal_download:
            message = ('Minimal download: '
                       + '{}\n\nMinimal download executed for #{}'.format(
                          self.title, self.issue)
                       + '\n\nOnly data that needs [no review](https://'
                       + 'github.com/pyvideo/pyvideo_scrape#use-cases) was scraped.'
                       + '\nThis event needs further scraping and human '
                       + 'reviewing for the description and other data to show.'
                       + message_body)
            repo.git.commit('-m', message)
            repo.git.push('--set-upstream', 'origin', self.branch)
        else:
            message = (
                'Scraped {}\n\nFixes #{}'.format(self.branch, self.issue)
                + message_body)
            repo.git.commit('-m', message)
        
        repo.git.checkout('main')
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

        return slugify.slugify(self.metadata['title'])

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

    def __init__(self, event):
        self.event = event
        self.filename = None
        self.metadata = {}

    @classmethod
    def from_file(cls, path, event):
        """Contructor. Retrieves video metadata from file"""
        self = cls(event)

        self.filename = path.stem  # Name without .json

        try:
            with path.open() as f_path:
                self.metadata = json.load(f_path)
        except ValueError:
            print('Json syntax error in file {}'.format(path))
            raise

        return self

    @classmethod
    def from_youtube(cls, video_data, event):
        """Contructor. Retrieves video metadata with youtube-dl"""
        self = cls(event)

        metadata = self.metadata

        metadata['title'] = self.__calculate_title(video_data)
        self.filename = self.__calculate_slug()
        metadata['speakers'] = ['TODO']  # Needs human intervention later
        # youtube_id = video_data['display_id']
        # metadata['thumbnail_url'] =
        #   'https://i.ytimg.com/vi/{}/maxresdefault.jpg'.format(youtube_id)
        metadata['thumbnail_url'] = video_data['thumbnail']
        metadata['videos'] = [{
            'type': 'youtube',
            'url': video_data['webpage_url']
        }]
        metadata['recorded'] = self.__calculate_date_recorded(
            video_data['upload_date'])

        # optional values
        # metadata['copyright_text'] = video_data['license']
        metadata['duration'] = video_data['duration']  # In seconds
        metadata['language'] = video_data['formats'][0].get(
            'language', event.language)
        if not metadata['language']:
            metadata['language'] = event.language
        metadata['related_urls'] = copy.deepcopy(event.related_urls)

        if event.minimal_download:
            metadata['speakers'] = []
            metadata['tags'] = event.tags
            metadata['description'] = ''
        else:
            metadata['tags'] = sorted(
                set(video_data['tags']).union(set(event.tags)))
            metadata['description'] = video_data['description']
            description_urls = list(
                set(
                    re.findall(r'http[s]?://[^ \\\n\t()[\]"`´\']+', video_data[
                        'description'])))
            for url in description_urls:
                metadata['related_urls'].append({'label': url, 'url': url})

        return self

    def merge(self, new_video, fields):
        """Create video copy overwriting fields """
        merged_video = Video(self.event)
        merged_video.filename = self.filename
        for field in self.metadata:
            if field in set(fields):
                merged_video.metadata[field] = new_video.metadata.get(field)
            else:
                merged_video.metadata[field] = self.metadata.get(field)
        return merged_video

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

        data_text = json.dumps(self.metadata, **JSON_FORMAT_KWARGS) + '\n'
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
    event_data_yaml, events_data = load_events(events_file)

    pyvideo_repo = pathlib.Path(
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
        except (GitCommandError, FileExistsError) as exc:
            logger.warning('Event {} skipped', event.branch)
            logger.debug(exc.args[0])
            continue
        event.download_video_data()
        event.load_video_data()
        event.merge_video_data()
        event.save_video_data()
        event.create_commit(event_data_yaml)

    time_end = datetime.datetime.now()
    time_delta = str(time_end - time_init)
    logger.debug('Time init: {}', time_init)
    logger.debug('Time end: {}', time_end)
    logger.debug('Time delta: {}', time_delta)


if __name__ == '__main__':
    main()
