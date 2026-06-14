from fastapi import APIRouter

from app.api.routes import auth, chat, health, merchant, payments, products

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(merchant.router, tags=["merchant"])
api_router.include_router(payments.router, tags=["payments"])
api_router.include_router(products.router, tags=["products"])
