import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.routers.deps import get_current_user
from app.schemas.common import ApiResponse
from app.schemas.recommendation import RecommendationResponse, RecommendationRequest

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.post(
    "",
    response_model=ApiResponse[RecommendationResponse],
    summary="Lấy gợi ý sản phẩm",
    description="Nhận `user_id` và `query`, gọi Core service `/recommend` và trả danh sách gợi ý.",
    response_description="Danh sách sản phẩm gợi ý cho user.",
    responses={
        401: {"description": "Thiếu hoặc sai token"},
        403: {"description": "Không có quyền lấy recommendation cho user khác"},
        404: {"description": "Không tìm thấy user"},
        502: {"description": "Lỗi kết nối hoặc lỗi phản hồi từ Core service"},
        422: {"description": "Dữ liệu đầu vào không hợp lệ"},
    },
)
async def get_recommendations(
    payload: RecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != payload.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only request your own recommendations")

    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    request_data = payload.model_dump()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{settings.core_service_url}/recommend", json=request_data)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Core service error: {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Cannot reach core service: {exc}") from exc

    data = response.json()
    return ApiResponse(
        data=RecommendationResponse(
            user_id=payload.user_id,
            query=payload.query,
            items=data.get("items", []),
        ),
        message="Recommendations retrieved",
        code=200,
    )
