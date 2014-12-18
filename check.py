import logging
import os
import re
import sys
import asyncio
from datetime import datetime, timezone
from urllib.error import URLError, HTTPError
from urllib.request import urlopen
from urllib.parse import urlparse, urljoin

import lxml.html
import aiohttp

USER_AGENT = 'crawlability-bot (+http://crawlability.capybala.com/)'
TITLE_RE = re.compile(r'<title>\s*(.*?)\s*</title>', re.DOTALL | re.IGNORECASE)


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


class Crawlability(DictLike):

    def to_cacheable_dict(self):
        d = dict(self)
        for page in [d.page, d.top_page, d.terms_page] + d.fuzzy_sitemaps:
            if not page:
                continue

            del page.text_body
            del page.bytes_body

        del d.robots_txt.bytes_body

        return d


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

    c = Crawlability()
    yield from asyncio.wait([
        get_page(c, url),
        get_top_page(c, top_url),
        get_robots_txt(c, top_url),
        get_fuzzy_sitemaps(c, top_url),
    ])

    return c


def get_page(c, url):
    page = yield from fetch(url)

    terms_link = None
    terms_page = None

    if page.ok:
        root = lxml.html.fromstring(page.bytes_body)
        terms_links = root.xpath('//a[text()="利用規約" or text()="Terms"]/@href')
        if len(terms_links):
            terms_link = urljoin(page.url, terms_links[0])

        if terms_link:
            terms_page = yield from try_fetch(terms_link)

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

    headers = {'User-Agent': USER_AGENT}
    begin = datetime.now(timezone.utc)
    f = yield from aiohttp.request('GET', url, headers=headers, allow_redirects=False)
    bytes_body = yield from f.read()
    end = datetime.now(timezone.utc)
    elapsed_ms = (end - begin).total_seconds() * 1000

    content_type = f.headers.get('Content-Type', '')

    logger.info('Downloaded. code: %s, type: %s, size: %sbytes, in %s milliseconds',
                f.status, content_type, len(bytes_body), elapsed_ms)
    text_body = bytes_body.decode('utf-8')
    logger.debug(text_body)

    title = ''
    if 'html' in content_type.lower():
        m = TITLE_RE.search(text_body)
        if m:
            title = m.group(1)

    return Response(
        url=url,
        user_agent=USER_AGENT,
        error=False,
        status=f.status,
        length=len(bytes_body),
        text_body=text_body,
        bytes_body=bytes_body,
        content_type=content_type,
        ok=(200 <= f.status < 300),
        started_at=begin,
        elapsed_ms=elapsed_ms,
        title=title,
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

setup_logger()
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    main()
