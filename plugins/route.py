from aiohttp import web
from bot import Bot  # Import Bot instance

async def web_server():
    app = web.Application()
    app.add_routes([
        web.get("/", root_route_handler),
        web.post("/webhook", handle_webhook)
    ])
    return app

async def handle_webhook(request):
    try:
        update = await request.json()
        await Bot.handle_update(update)  # Pass to Pyrogram
        return web.Response(status=200)
    except Exception as e:
        print(f"Webhook error: {e}")  # Temporary print for debugging
        return web.Response(status=500)

async def root_route_handler(request):
    return web.json_response("NocoFlux")