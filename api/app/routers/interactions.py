from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.interaction import Interaction
from app.models.product import Product
from app.models.user import User
from app.routers.deps import get_current_user
from app.schemas.common import ApiResponse
from app.schemas.interaction import InteractionCreateRequest, InteractionResponse

router = APIRouter(prefix="/interactions", tags=["Interactions"])


@router.post(
    "",
    response_model=ApiResponse[InteractionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Ghi nhận hành vi người dùng",
    description="Ghi lại hành vi `view` hoặc `purchase` của user trên sản phẩm.",
    response_description="Bản ghi interaction vừa được tạo.",
    responses={
        401: {"description": "Thiếu hoặc sai token"},
        403: {"description": "Không có quyền ghi interaction cho user khác"},
        404: {"description": "Không tìm thấy user hoặc product"},
        422: {"description": "Dữ liệu đầu vào không hợp lệ"},
    },
)
def create_interaction(
    payload: InteractionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != payload.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only write your own interactions")

    user = db.query(User).filter(User.id == payload.user_id).first()
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not user or not product:
        raise HTTPException(status_code=404, detail="User or product not found")

    interaction = Interaction(
        user_id=payload.user_id,
        product_id=payload.product_id,
        action_type=payload.action_type,
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    return ApiResponse(
        data=InteractionResponse.model_validate(interaction),
        message="Interaction created",
        code=status.HTTP_201_CREATED,
    )
