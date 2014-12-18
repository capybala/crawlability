import os
import sys
import asyncio
import json

from aiohttp import web
from jinja2 import Environment, FileSystemLoader
import pylibmc

from check import check, Crawlability


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

MEMCACHIER_SERVERS = os.environ.get('MEMCACHIER_SERVERS', '').split(',')
MEMCACHIER_USERNAME = os.environ.get('MEMCACHIER_USERNAME', '')
MEMCACHIER_PASSWORD = os.environ.get('MEMCACHIER_PASSWORD', '')

CACHE_DISABLED = os.environ.get('CACHE_DISABLED') == '1'
CACHE_TIMEOUT_SECONDS = 5 * 60

mc = pylibmc.Client(MEMCACHIER_SERVERS, binary=True,
                    username=MEMCACHIER_USERNAME, password=MEMCACHIER_PASSWORD,
                    behaviors={"tcp_nodelay": True,
                               "ketama": True,
                               "no_block": True,})


def _get_from_cache(bytes_url):
    if CACHE_DISABLED:
        return None

    value = mc.get(bytes_url)
    if value is None:
        return None

    d = json.loads(value)
    c = Crawlability(**d)
    return c


def _store_into_cache(bytes_url, c):
    if CACHE_DISABLED:
        return

    mc.set(bytes_url, json.dumps(c.to_cacheable_dict()), time=CACHE_TIMEOUT_SECONDS)


@asyncio.coroutine
def handle_index(request):
    template = env.get_template('index.html')
    return web.Response(body=template.render().encode('utf-8'))


@asyncio.coroutine
def handle_result(request):
    url = request.GET.get('url')

    bytes_url = url.encode('utf-8')
    if len(bytes_url) > 250:
        return web.Response(status=400, body='url parameter is too long')

    c = _get_from_cache(bytes_url)
    if c is None:
        c = yield from check(url)
        _store_into_cache(bytes_url, c)

    template = env.get_template('result.html')
    return web.Response(body=template.render(c=c).encode('utf-8'))

    text = 'Status: {0}'.format(c.page.status)
    return web.Response(body=text.encode('utf-8'), content_type='text/html; charset=utf-8')


@asyncio.coroutine
def init(loop):
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/result', handle_result)
    app.router.add_route('GET', '/', handle_index)
    app.router.add_static('/static', STATIC_DIR)

    host = '0.0.0.0'
    port = os.environ.get('PORT', 8000)
    srv = yield from loop.create_server(app.make_handler(), host, port)
    print("Server started at http://{0}:{1}".format(host, port))
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
try:
    loop.run_forever()
except KeyboardInterrupt:
    print('Interrupted', file=sys.stderr)
