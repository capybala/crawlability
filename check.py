import logging
import os
import re
import sys
from urllib.error import URLError, HTTPError
from urllib.request import urlopen
from urllib.parse import urlparse


class DictLike(dict):
    def __getattr__(self, name):
        if name in self:
            return self[name]
        else:
            raise AttributeError("No such attribute: " + name)

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        if name in self:
            del self[name]
        else:
            raise AttributeError("No such attribute: " + name)


class Response(DictLike):
    pass


class Compatiblity(DictLike):
    pass


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

    page = fetch(url)

    top_url = '{0.scheme}://{0.netloc}/'.format(o)
    if top_url == url:
        top_page = page
    else:
        top_page = try_fetch(top_url)

    robots_url = top_url + 'robots.txt'

    robots_txt = try_fetch(robots_url)
    if robots_txt.error:
        sitemap_urls = []
    else:
        sitemap_urls = re.findall(r'^sitemap:\s*(.*)$',
                                  robots_txt.body, re.IGNORECASE | re.MULTILINE)

    fuzzy_sitemap_urls = [
        top_url + 'sitemap.xml',
        top_url + 'sitemaps.xml',
    ]
    fuzzy_sitemaps = []
    for fuzzy_sitemap_url in fuzzy_sitemap_urls:
        if fuzzy_sitemap_url not in sitemap_urls:
            fuzzy_sitemaps.append(try_fetch(fuzzy_sitemap_url))

    c = Compatiblity(
        page=page,
        top_page=top_page,
        robots_txt=robots_txt,
        sitemap_urls=sitemap_urls,
        fuzzy_sitemaps=fuzzy_sitemaps,
    )
    print(c)


def fetch(url):
    logger.info('Downloading %s', url)
    f = urlopen(url)
    bytes_body = f.read()
    logger.info('Downloaded. code: %s, size: %sbytes', f.status, len(bytes_body))
    text_body = bytes_body.decode('utf-8')
    logger.debug(text_body)
    return Response(
        url=url,
        error=False,
        status=f.status,
        length=len(bytes_body),
        body=text_body,
    )


def try_fetch(url):
    try:
        return fetch(url)
    except HTTPError as ex:
        return Response(
            url=url,
            error=True,
            status=ex.code,
            reason=ex.reason,
        )
    except URLError as ex:
        return Response(
            url=url,
            error=True,
            reason=ex.reason,
        )

if __name__ == '__main__':
    setup_logger()
    logger = logging.getLogger(__name__)
    main()
