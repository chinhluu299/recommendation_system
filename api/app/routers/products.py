from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.product import Product
from app.routers.deps import get_current_user
from app.schemas.common import ApiResponse
from app.schemas.product import ProductResponse, ProductSearchResponse

router = APIRouter(prefix="/products", tags=["Products"])


@router.get(
    "/search",
    response_model=ApiResponse[ProductSearchResponse],
    summary="Tìm kiếm sản phẩm",
    description="Tìm sản phẩm theo từ khóa từ title, brand, description, category.",
    response_description="Danh sách sản phẩm phù hợp với từ khóa.",
    responses={
        401: {"description": "Thiếu hoặc sai token"},
        422: {"description": "Query params không hợp lệ"},
    },
)
def search_products(
    query: str = Query(..., min_length=1, description="Từ khóa tìm kiếm, ví dụ: iphone"),
    limit: int = Query(20, ge=1, le=100, description="Số lượng bản ghi trả về"),
    offset: int = Query(0, ge=0, description="Số bản ghi bỏ qua để phân trang"),
    _: object = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    keyword = f"%{query}%"
    filters = or_(
        Product.title.ilike(keyword),
        Product.brand.ilike(keyword),
        Product.description.ilike(keyword),
        Product.category.ilike(keyword),
    )

    total = db.query(func.count(Product.id)).filter(filters).scalar() or 0
    items = (
        db.query(Product)
        .filter(filters)
        .order_by(Product.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return ApiResponse(
        data=ProductSearchResponse(items=items, total=total, query=query),
        message="Search successful",
        code=200,
    )


@router.get(
    "/{product_id}",
    response_model=ApiResponse[ProductResponse],
    summary="Lấy chi tiết sản phẩm",
    description="Trả về toàn bộ thông tin của một sản phẩm theo product_id.",
    response_description="Chi tiết sản phẩm.",
    responses={
        401: {"description": "Thiếu hoặc sai token"},
        404: {"description": "Không tìm thấy sản phẩm"},
    },
)
def get_product_detail(
    product_id: int = Path(..., ge=1, description="ID sản phẩm"),
    _: object = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ApiResponse(
        data=ProductResponse.model_validate(product),
        message="Product detail retrieved",
        code=200,
    )
