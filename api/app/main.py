from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import Base, engine
from app.models import Interaction, Product, User  # noqa: F401
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.interactions import router as interactions_router
from app.routers.products import router as products_router
from app.routers.recommendations import router as recommendations_router
from app.routers.users import router as users_router

Base.metadata.create_all(bind=engine)

tags_metadata = [
    {"name": "Health", "description": "Kiểm tra trạng thái API."},
    {"name": "Auth", "description": "Đăng ký và đăng nhập lấy JWT token."},
    {"name": "Users", "description": "Danh sách user cho demo login."},
    {"name": "Products", "description": "Tìm kiếm và lấy chi tiết sản phẩm."},
    {"name": "Interactions", "description": "Ghi nhận hành vi người dùng (view/purchase)."},
    {"name": "Recommendations", "description": "Lấy danh sách gợi ý từ Core service."},
]

app = FastAPI(
    title=settings.app_name,
    description="Prototype API cho website thương mại điện tử với hệ thống gợi ý sản phẩm điện thoại.",
    version="1.0.0",
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(interactions_router, prefix="/api/v1")
app.include_router(recommendations_router, prefix="/api/v1")


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "data": None,
            "message": str(exc.detail),
            "code": exc.status_code,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "data": exc.errors(),
            "message": "Validation error",
            "code": 422,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(_: Request, _exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "data": None,
            "message": "Internal server error",
            "code": 500,
        },
    )
