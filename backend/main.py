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


# using lifespane events to manage startup and shutdown tasks
# This allows us to run async functions during startup and shutdown

async def lifespan(app: FastAPI):
    await asyncio.to_thread(init_db)
    await asyncio.to_thread(_initial_seed)
    await asyncio.to_thread(_initial_fetch)
    asyncio.create_task(poll_loop())
    asyncio.create_task(summarize_loop())
    asyncio.create_task(dispatch_loop())
    asyncio.create_task(plugin_loop())
    
    yield  # This will keep the app running until shutdown

app = FastAPI(lifespan=lifespan)
app.include_router(api_router, prefix="/api")

#! Commented out the startup and shutdown events since we are using lifespan
# @app.on_event("startup")
# async def on_startup():
#     await asyncio.to_thread(init_db)
#     await asyncio.to_thread(_initial_seed)
#     await asyncio.to_thread(_initial_fetch)
#     asyncio.create_task(poll_loop())
#     asyncio.create_task(summarize_loop())
#     asyncio.create_task(dispatch_loop())
#     asyncio.create_task(plugin_loop())
    
    
# @app.on_event("shutdown")
# async def on_shutdown():
#     # Perform any necessary cleanup here
#     print("Shutting down the application...")
#     # For example, close database connections or stop background tasks
#     # await asyncio.sleep(1)  # Simulate cleanup delay if needed
#     print("Application shutdown complete.")