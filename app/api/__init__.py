# app/api/__init__.py
from fastapi import APIRouter
from .dates import router as dates_router
from .countries import router as countries_router
from .events import router as events_router

router = APIRouter()
router.include_router(dates_router)
router.include_router(countries_router)
router.include_router(events_router)
