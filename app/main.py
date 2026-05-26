from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_audit import router as audit_router
from app.api.routes_conference import router as conference_router
from app.api.routes_decision import router as decision_router
from app.api.routes_health import router as health_router
from app.api.routes_orders import router as orders_router
from app.api.routes_portfolio import router as portfolio_router
from app.api.routes_proposals import router as proposals_router
from app.api.routes_production import router as production_router
from app.api.routes_provider import router as provider_router
from app.api.routes_settings import router as settings_router
from app.api.routes_test import router as test_router
from app.api.dependencies import require_operator_auth
from app.brokers.models import BrokerProviderError
from app.core.logging import configure_logging
from app.storage.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    yield


app = FastAPI(title="ConsensusAlpha", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

protected = [Depends(require_operator_auth)]

app.include_router(health_router)
app.include_router(settings_router, dependencies=protected)
app.include_router(provider_router, dependencies=protected)
app.include_router(portfolio_router, dependencies=protected)
app.include_router(proposals_router, dependencies=protected)
app.include_router(conference_router, dependencies=protected)
app.include_router(decision_router, dependencies=protected)
app.include_router(orders_router, dependencies=protected)
app.include_router(audit_router, dependencies=protected)
app.include_router(production_router, dependencies=protected)
app.include_router(test_router, dependencies=protected)


@app.exception_handler(BrokerProviderError)
async def broker_provider_error_handler(_: Request, exc: BrokerProviderError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"detail": {"code": exc.code, "message": str(exc), "details": exc.details}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors()})
