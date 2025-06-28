import asyncio

from fastapi import FastAPI

from app.api.views import router as api_router
from app.core import (
    _initial_seed,
    _initial_fetch,
    poll_loop,
    summarize_loop,
    dispatch_loop,
    plugin_loop,
)
from app.db import init_db

app = FastAPI()
app.include_router(api_router, prefix="/api")

@app.on_event("startup")
async def on_startup():
    await asyncio.to_thread(init_db)
    await asyncio.to_thread(_initial_seed)
    await asyncio.to_thread(_initial_fetch)
    asyncio.create_task(poll_loop())
    asyncio.create_task(summarize_loop())
    asyncio.create_task(dispatch_loop())
    asyncio.create_task(plugin_loop())