import logging
import os
import re
import sys
import asyncio
from urllib.error import URLError, HTTPError
from urllib.request import urlopen
from urllib.parse import urlparse, urljoin

import lxml.html
import aiohttp


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

    loop = asyncio.get_event_loop()
    c = loop.run_until_complete(check(url))
    #print(c)


def check(url):
    o = urlparse(url)

    if o.scheme not in ('http', 'https'):
        raise ValueError('Invalid url')

    top_url = '{0.scheme}://{0.netloc}/'.format(o)

    c = Compatiblity()
    yield from asyncio.wait([
        get_page(c, url),
        get_top_page(c, top_url),
        get_robots_txt(c, top_url),
        get_fuzzy_sitemaps(c, top_url),
    ])

    return c


def get_page(c, url):
    page = yield from fetch(url)

    root = lxml.html.fromstring(page.bytes_body)
    terms_links = root.xpath('//a[text()="利用規約" or text()="Terms"]/@href')
    if len(terms_links):
        terms_link = urljoin(page.url, terms_links[0])
    else:
        terms_link = None

    if terms_link:
        terms_page = yield from try_fetch(terms_link)
    else:
        terms_page = None

    c.page = page
    c.terms_link = terms_link
    c.terms_page = terms_page


def get_top_page(c, top_url):
    c.top_page = yield from try_fetch(top_url)


def get_robots_txt(c, top_url):
    robots_url = top_url + 'robots.txt'

    robots_txt = yield from try_fetch(robots_url)
    if robots_txt.error:
        sitemap_urls = []
    else:
        sitemap_urls = re.findall(r'^sitemap:\s*(.*)$',
                                  robots_txt.text_body, re.IGNORECASE | re.MULTILINE)

    c.robots_txt = robots_txt
    c.sitemap_urls = sitemap_urls


def get_fuzzy_sitemaps(c, top_url):
    fuzzy_sitemap_urls = [
        top_url + 'sitemap.xml',
        top_url + 'sitemaps.xml',
    ]
    fuzzy_sitemaps = []
    for fuzzy_sitemap_url in fuzzy_sitemap_urls:
        fuzzy_sitemaps.append((yield from try_fetch(fuzzy_sitemap_url)))

    c.fuzzy_sitemaps = fuzzy_sitemaps


def fetch(url):
    logger.info('Downloading %s', url)
    f = yield from aiohttp.request('GET', url)
    bytes_body = yield from f.read()
    logger.info('Downloaded. code: %s, size: %sbytes', f.status, len(bytes_body))
    text_body = bytes_body.decode('utf-8')
    logger.debug(text_body)
    return Response(
        url=url,
        error=False,
        status=f.status,
        length=len(bytes_body),
        text_body=text_body,
        bytes_body=bytes_body,
    )


def try_fetch(url):
    try:
        return fetch(url)
    except HTTPError as ex:
        logger.info('HTTPError code: %s, reason: %s', ex.code, ex.reason)
        return Response(
            url=url,
            error=True,
            status=ex.code,
            reason=ex.reason,
        )
    except URLError as ex:
        logger.info('URLError reason: %s', ex.reason)
        return Response(
            url=url,
            error=True,
            reason=ex.reason,
        )

if __name__ == '__main__':
    setup_logger()
    logger = logging.getLogger(__name__)
    main()
