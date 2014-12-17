import asyncio
from aiohttp import web

from check import check


@asyncio.coroutine
def handle(request):
    name = request.match_info.get('name', "Anonymous")
    text = "Hello, " + name
    return web.Response(body=text.encode('utf-8'))


@asyncio.coroutine
def handle_check(request):
    url = request.GET.get('url')
    c = yield from check(url)
    text = 'Status: {0}'.format(c.page.status)
    return web.Response(body=text.encode('utf-8'))


@asyncio.coroutine
def init(loop):
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/check', handle_check)
    app.router.add_route('GET', '/{name}', handle)

    srv = yield from loop.create_server(app.make_handler(),
                                        '127.0.0.1', 8000)
    print("Server started at http://127.0.0.1:8000")
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
