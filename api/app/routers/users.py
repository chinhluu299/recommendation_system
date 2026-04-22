from collections import Counter

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.interaction import Interaction
from app.models.product import Product
from app.models.user import User
from app.routers.deps import get_current_user
from app.schemas.common import ApiResponse
from app.schemas.user import (
    UserInteractedProduct,
    UserInteractionsResponse,
    UserTrendInsightRequest,
    UserTrendInsightResponse,
    UserListResponse,
    UserSummary,
)

router = APIRouter(prefix="/users", tags=["Users"])

MIN_INTERACTIONS = 5


@router.get(
    "",
    response_model=ApiResponse[UserListResponse],
    summary="Danh sách user có thể login (demo)",
    description=f"Trả về các user có ít nhất {MIN_INTERACTIONS} interactions. Không yêu cầu auth.",
)
def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    # Đếm interactions per user, lọc >= MIN_INTERACTIONS
    subq = (
        db.query(
            Interaction.user_id,
            func.count(Interaction.id).label("cnt"),
        )
        .group_by(Interaction.user_id)
        .having(func.count(Interaction.id) >= MIN_INTERACTIONS)
        .subquery()
    )

    rows = (
        db.query(User, subq.c.cnt)
        .join(subq, User.id == subq.c.user_id)
        .filter(User.external_user_id.isnot(None))
        .order_by(subq.c.cnt.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    total = (
        db.query(func.count())
        .select_from(
            db.query(Interaction.user_id)
            .group_by(Interaction.user_id)
            .having(func.count(Interaction.id) >= MIN_INTERACTIONS)
            .subquery()
        )
        .scalar()
        or 0
    )

    items = [
        UserSummary(
            id=user.id,
            external_user_id=user.external_user_id,
            full_name=user.full_name,
            interaction_count=cnt,
        )
        for user, cnt in rows
    ]

    return ApiResponse(
        data=UserListResponse(items=items, total=total),
        message="Users retrieved",
        code=200,
    )


@router.get(
    "/me/interactions",
    response_model=ApiResponse[UserInteractionsResponse],
    summary="Danh sách sản phẩm user đã tương tác",
    description=(
        "Trả về danh sách sản phẩm mà user hiện tại đã từng tương tác "
        "(view/purchase), gộp theo product và sắp theo lần tương tác gần nhất."
    ),
)
def list_my_interactions(
    action_type: str | None = Query(
        default=None,
        pattern="^(view|purchase)$",
        description="Lọc theo loại hành vi (view hoặc purchase). Để trống để lấy tất cả.",
    ),
    limit: int = Query(default=20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = [Interaction.user_id == current_user.id]
    if action_type:
        filters.append(Interaction.action_type == action_type)

    rows = (
        db.query(
            Product.id.label("product_id"),
            Product.title.label("title"),
            Product.brand.label("brand"),
            Product.price.label("price"),
            Product.image_url.label("image_url"),
            func.max(Interaction.created_at).label("last_interacted_at"),
            func.count(Interaction.id).label("interaction_count"),
            func.sum(case((Interaction.action_type == "purchase", 1), else_=0)).label(
                "purchase_count"
            ),
        )
        .join(Product, Product.id == Interaction.product_id)
        .filter(*filters)
        .group_by(Product.id, Product.title, Product.brand, Product.price, Product.image_url)
        .order_by(func.max(Interaction.created_at).desc())
        .limit(limit)
        .all()
    )

    items: list[UserInteractedProduct] = []
    for row in rows:
        last_action = (
            db.query(Interaction.action_type)
            .filter(
                Interaction.user_id == current_user.id,
                Interaction.product_id == row.product_id,
            )
            .order_by(Interaction.created_at.desc())
            .first()
        )
        items.append(
            UserInteractedProduct(
                product_id=row.product_id,
                title=row.title,
                brand=row.brand,
                price=row.price,
                image_url=row.image_url,
                last_action_type=last_action[0] if last_action else "view",
                last_interacted_at=row.last_interacted_at,
                interaction_count=int(row.interaction_count or 0),
                purchase_count=int(row.purchase_count or 0),
            )
        )

    return ApiResponse(
        data=UserInteractionsResponse(items=items, total=len(items)),
        message="User interactions retrieved",
        code=200,
    )


def _build_fallback_insight(
    query: str,
    interaction_count: int,
    purchase_count: int,
    top_brands: list[str],
    top_categories: list[str],
) -> str:
    purchase_ratio = (
        round((purchase_count / interaction_count) * 100) if interaction_count > 0 else 0
    )
    brands_text = ", ".join(top_brands) if top_brands else "chưa rõ thương hiệu nổi trội"
    categories_text = (
        ", ".join(top_categories) if top_categories else "chưa rõ danh mục nổi trội"
    )

    return (
        f"Với truy vấn \"{query}\", user này có xu hướng ưu tiên các sản phẩm thuộc nhóm "
        f"{categories_text}, thiên về thương hiệu {brands_text}. "
        f"Tỷ lệ purchase trên tổng tương tác đang ở mức khoảng {purchase_ratio}%, cho thấy "
        "mức độ sẵn sàng mua cao hơn ở các sản phẩm trùng với pattern đã tương tác gần đây."
    )


@router.post(
    "/me/interaction-trend-insight",
    response_model=ApiResponse[UserTrendInsightResponse],
    summary="Phân tích xu hướng user theo query (LLM)",
    description=(
        "Nhận query từ UI, dùng lịch sử tương tác của user hiện tại và tạo tóm tắt xu hướng "
        "ưu tiên bằng LLM để đối chiếu với kết quả recommendation."
    ),
)
def get_my_interaction_trend_insight(
    payload: UserTrendInsightRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = payload.query.strip()
    if not query:
        return ApiResponse(
            data=None,
            message="Query must not be empty",
            code=400,
        )

    lookback_limit = max(20, min(payload.lookback_limit, 300))
    rows = (
        db.query(
            Interaction.action_type,
            Product.title,
            Product.brand,
            Product.category,
            Product.price,
        )
        .join(Product, Product.id == Interaction.product_id)
        .filter(Interaction.user_id == current_user.id)
        .order_by(Interaction.created_at.desc())
        .limit(lookback_limit)
        .all()
    )

    interaction_count = len(rows)
    purchase_count = sum(1 for row in rows if row.action_type == "purchase")
    top_brands = [
        brand
        for brand, _ in Counter(
            [row.brand for row in rows if row.brand and row.brand.strip()]
        ).most_common(3)
    ]
    top_categories = [
        category
        for category, _ in Counter(
            [row.category for row in rows if row.category and row.category.strip()]
        ).most_common(3)
    ]

    fallback_insight = _build_fallback_insight(
        query=query,
        interaction_count=interaction_count,
        purchase_count=purchase_count,
        top_brands=top_brands,
        top_categories=top_categories,
    )

    if interaction_count == 0:
        return ApiResponse(
            data=UserTrendInsightResponse(
                query=query,
                insight=(
                    f"Chưa có interaction trong DB để phân tích xu hướng cho truy vấn \"{query}\"."
                ),
                interaction_count=0,
                purchase_count=0,
                top_brands=[],
                top_categories=[],
            ),
            message="No interactions to analyze",
            code=200,
        )

    recent_records_text = "\n".join(
        [
            (
                f"- title: {row.title}; brand: {row.brand}; category: {row.category}; "
                f"price: {row.price}; action: {row.action_type}"
            )
            for row in rows[:60]
        ]
    )

    prompt = (
        "Bạn là AI analyst cho hệ recommendation ecommerce.\n"
        "Nhiệm vụ: dựa trên query hiện tại + lịch sử interaction gần đây, viết ngắn gọn xu hướng ưu tiên của user.\n"
        "Yêu cầu output tiếng Việt, 3-5 câu, rõ ràng và có thể dùng để đối chiếu với kết quả ranking.\n"
        "Nên nêu: mức nhạy giá, thiên hướng brand/category, xu hướng mua vs xem, và kiểu sản phẩm khả năng cao user ưu tiên.\n\n"
        f"Query: {query}\n"
        f"Tổng interactions: {interaction_count}, purchases: {purchase_count}\n"
        f"Top brands: {top_brands}\n"
        f"Top categories: {top_categories}\n"
        f"Recent interactions:\n{recent_records_text}\n"
    )

    insight_text = fallback_insight
    try:
        from offline.query_engine._llm_client import chat

        llm_output = chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3,
        ).strip()
        if llm_output:
            insight_text = llm_output
    except Exception:
        insight_text = fallback_insight

    return ApiResponse(
        data=UserTrendInsightResponse(
            query=query,
            insight=insight_text,
            interaction_count=interaction_count,
            purchase_count=purchase_count,
            top_brands=top_brands,
            top_categories=top_categories,
        ),
        message="Trend insight generated",
        code=200,
    )
