import logging
import os
import re
import sys
from urllib.request import urlopen
from urllib.parse import urlparse


def setup_logger():
    level = logging.INFO
    if os.environ.get('DEBUG') == '1':
        level = logging.DEBUG
    logging.basicConfig(level=level)


def main():
    url = sys.argv[1]
    check(url)


def check(url):
    o = urlparse(url)

    if o.scheme not in ('http', 'https'):
        raise ValueError('Invalid url')

    top_url = '{0.scheme}://{0.netloc}/'.format(o)
    robots_url = top_url + 'robots.txt'

    robots_txt = fetch(robots_url)
    sitemaps = re.findall(r'^sitemap:\s*(.*)$', robots_txt, re.IGNORECASE | re.MULTILINE)

    print(sitemaps)


def fetch(url):
    logger.info('Downloading %s', url)
    f = urlopen(url)
    bytes_body = f.read()
    logger.info('Downloaded. code: %s, size: %sbytes', f.status, len(bytes_body))
    text_body = bytes_body.decode('utf-8')
    logger.debug(text_body)
    return text_body


if __name__ == '__main__':
    setup_logger()
    logger = logging.getLogger(__name__)
    main()
