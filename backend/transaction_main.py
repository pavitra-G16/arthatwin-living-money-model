from contextlib import asynccontextmanager

from fastapi import FastAPI

from transaction_api import router
from transaction_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ArthaTwin Transaction Intelligence API",
    description="Deterministic local transaction ingestion, categorization, and correction rules.",
    version="0.2.0",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/")
def root():
    return {"name": "ArthaTwin Transaction Intelligence", "docs": "/docs", "api": "/api"}
