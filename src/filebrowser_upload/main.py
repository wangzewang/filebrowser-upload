# coding: utf-8
import argparse
import sys
import warnings
from os.path import abspath, join, dirname, expanduser

VENDOR_PATH = abspath(join(dirname(__file__), 'vendor'))
sys.path.insert(0, VENDOR_PATH)

import requests
from tqdm import tqdm
from urllib3.exceptions import InsecureRequestWarning
from .__version__ import __version__

warnings.simplefilter('ignore', InsecureRequestWarning)

try:
    from requests.utils import super_len
except ImportError:
    super_len = len


def get_args():
    if '--version' in sys.argv:
        print(__version__)
        sys.exit(0)
    parser = argparse.ArgumentParser(description='Filebrowser upload.')
    parser.add_argument('filepath', help='local file path')
    parser.add_argument('--version', dest='version', help='Show version')
    parser.add_argument('--api',
                        dest='api',
                        required=True,
                        help='Filebrowser upload API URL')
    parser.add_argument('--username',
                        dest='username',
                        required=True,
                        help='Username')
    parser.add_argument('--password',
                        dest='password',
                        required=True,
                        help='Password')
    parser.add_argument('--dest',
                        dest='dest',
                        required=True,
                        help='File destination')
    parser.add_argument(
        '--insecure',
        dest='insecure',
        action='store_true',
        default=False,
        help='Allow insecure server connections when using SSL')
    parser.add_argument('--no-progress',
                        dest='no_progress',
                        action='store_true',
                        default=False,
                        help='Disable progress bar')
    parser.add_argument('--override',
                        dest='override',
                        action='store_true',
                        default=False,
                        help='Override file or not')

    parser.add_argument('--dir',
                        dest='dir',
                        action='store_true',
                        default=False,
                        help='Upload dir or not')
    args = parser.parse_args()
    args.api = args.api.strip().rstrip('/')
    args.dest = args.dest.strip().lstrip('/')
    args.filepath = expanduser(args.filepath)
    return args


def get_login_url(CONFIG):
    return '{}/login'.format(CONFIG.api)


def get_upload_url(CONFIG):
    return '{}/resources/{}'.format(CONFIG.api, CONFIG.dest)


def get_token(CONFIG):
    response = requests.post(get_login_url(CONFIG),
                             json={
                                 "password": CONFIG.password,
                                 "recaptcha": "",
                                 "username": CONFIG.username,
                             },
                             verify=not CONFIG.insecure)
    response.raise_for_status()
    return response.text


class ProgressFile:

    def __init__(self, fileobj):
        self.fileobj = fileobj
        self._length = super_len(self.fileobj)
        self.bar = tqdm(total=self._length,
                        ncols=80,
                        ascii=True,
                        unit='B',
                        unit_scale=True)

    def __len__(self):
        return self._length

    def read(self, size=-1):
        data = self.fileobj.read(size)
        self.bar.update(len(data))
        return data

    def close(self):
        self.bar.close()
        self.fileobj.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def upload(CONFIG):
    base_url = get_upload_url(CONFIG)
    print('Upload to {}'.format(base_url))
    try:
        token = get_token(CONFIG)
    except requests.exceptions.HTTPError as ex:
        print('Login failed: {} {}'.format(ex.response.status_code,
                                           ex.response.reason))
        return
    override = 'true' if CONFIG.override else 'false'
    is_dir = True if CONFIG.dir else False
    if not is_dir:
        fileobj = open(CONFIG.filepath, 'rb')
        if not CONFIG.no_progress:
            fileobj = ProgressFile(fileobj)
        headers = {
            'X-Auth': token,  # version >= 2.0.3 seems use this header
            'Authorization': 'Bearer {}'.format(
                token),  # version <= 2.0.0 seems use this header
        }
        with fileobj:
            response = requests.post(
                base_url,
                data=fileobj,
                params={"override": override},
                headers=headers,
                verify=not CONFIG.insecure,
            )
        print('{} {}'.format(response.status_code, response.reason))
    else:
        import os
        for path, _, files in os.walk(CONFIG.filepath):
            for f in files:
                fileobj = open(os.path.join(path, f), 'rb')
                file_path = path.lstrip("./")
                base_url = base_url.rstrip("/")
                url = f"{base_url}/{file_path}/{f}"
                print('--------------')
                print('Upload to {}'.format(url))
                print('file path to {}'.format(os.path.join(path, f)))
                if not CONFIG.no_progress:
                    fileobj = ProgressFile(fileobj)
                headers = {
                    'X-Auth': token,  # version >= 2.0.3 seems use this header
                    'Authorization': 'Bearer {}'.format(
                        token),  # version <= 2.0.0 seems use this header
                }
                with fileobj:
                    response = requests.post(
                        url,
                        data=fileobj,
                        params={"override": override},
                        headers=headers,
                        verify=not CONFIG.insecure,
                    )
                print('{} {}'.format(response.status_code, response.reason))


def main():
    upload(get_args())
