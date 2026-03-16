from fastapi import APIRouter

from app.schemas.common import ApiResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=ApiResponse[dict],
    summary="Health check",
    description="Kiểm tra nhanh trạng thái service.",
    response_description="Trạng thái hoạt động của API.",
)
def health_check():
    return ApiResponse(data={"status": "ok"}, message="Service healthy", code=200)
