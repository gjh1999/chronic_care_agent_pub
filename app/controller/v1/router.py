from fastapi import APIRouter

from app.controller.v1.auth import router as auth_router
from app.controller.v1.conversation import router as conversation_router
from app.controller.v1.health import router as health_router
from app.controller.v1.plan import router as plan_router
from app.controller.v1.reminder import router as reminder_router
from app.controller.v1.user import router as user_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(conversation_router)
router.include_router(health_router)
router.include_router(plan_router)
router.include_router(reminder_router)
router.include_router(user_router)
