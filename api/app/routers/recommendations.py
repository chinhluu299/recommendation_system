from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

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
    description="Nhận `user_id` và `query`, chạy pipeline offline và trả danh sách gợi ý.",
    response_description="Danh sách sản phẩm gợi ý cho user.",
    responses={
        401: {"description": "Thiếu hoặc sai token"},
        403: {"description": "Không có quyền lấy recommendation cho user khác"},
        404: {"description": "Không tìm thấy user"},
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

    try:
        from offline.search_pipeline import search_ranked
        asins = search_ranked(payload.query, user_id=str(user.id))
        items = [{"asin": a, "rank": i + 1} for i, a in enumerate(asins[:20])]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc

    return ApiResponse(
        data=RecommendationResponse(
            user_id=payload.user_id,
            query=payload.query,
            items=items,
        ),
        message="Recommendations retrieved",
        code=200,
    )
