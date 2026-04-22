import logging
import json
import re
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.interaction import Interaction
from app.models.product import Product
from app.models.user import User
from app.routers.deps import get_current_user
from app.schemas.common import ApiResponse
from app.schemas.product import (
    ProductResponse,
    ProductSearchResponse,
    RankingEvaluationRequest,
    RankingEvaluationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["Products"])


def _fallback_search(db: Session, query: str, limit: int, offset: int):
    """ILIKE search fallback khi pipeline không sẵn sàng.
    Tách query thành từng từ, mỗi từ phải xuất hiện trong ít nhất một cột.
    """
    words = [w.strip() for w in query.split() if w.strip()]
    if not words:
        return [], 0

    # Mỗi từ phải khớp ít nhất một trong các cột (AND giữa các từ)
    word_filters = []
    for word in words:
        kw = f"%{word}%"
        word_filters.append(
            or_(
                Product.title.ilike(kw),
                Product.brand.ilike(kw),
                Product.description.ilike(kw),
                Product.category.ilike(kw),
            )
        )

    from sqlalchemy import and_
    combined = and_(*word_filters)
    total = db.query(func.count(Product.id)).filter(combined).scalar() or 0
    items = (
        db.query(Product)
        .filter(combined)
        .order_by(Product.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return items, total


def _extract_json_object(raw_text: str) -> dict | None:
    raw = raw_text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except Exception:
        return None


@router.get(
    "/search",
    response_model=ApiResponse[ProductSearchResponse],
    summary="Tìm kiếm sản phẩm (Knowledge Graph + KGAT rerank)",
    description=(
        "Chạy pipeline offline (Neo4j + KGAT reranker) trực tiếp. "
        "Fallback về ILIKE search nếu pipeline không sẵn sàng."
    ),
    response_description="Danh sách sản phẩm đã xếp hạng.",
    responses={
        401: {"description": "Thiếu hoặc sai token"},
        422: {"description": "Query params không hợp lệ"},
    },
)
async def search_products(
    query: str = Query(..., min_length=1, description="Câu hỏi tìm kiếm, ví dụ: điện thoại pin lớn"),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_trace: bool = Query(
        default=False,
        description="Bật để trả trace các bước xử lý KG + KGAT.",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    external_user_id = current_user.external_user_id

    # ── Gọi pipeline offline trực tiếp ───────────────────────────────────────
    ranked_asins: list[str] = []
    search_trace: dict | None = None
    used_pipeline = False
    pipeline_error: str | None = None

    try:
        from app.search_pipeline import search_ranked, search_ranked_with_trace
        if include_trace:
            ranked_asins, search_trace = search_ranked_with_trace(
                query=query,
                user_id=external_user_id,
            )
        else:
            ranked_asins = search_ranked(query, user_id=external_user_id)
        used_pipeline = True
    except Exception as e:
        pipeline_error = str(e)
        if include_trace:
            search_trace = {
                "query": query,
                "pipeline_mode": "pipeline_error",
                "error": pipeline_error,
                "steps": [
                    {
                        "id": "pipeline_error",
                        "title": "Pipeline Error",
                        "payload": {"message": pipeline_error},
                    }
                ],
            }
        logger.warning("Pipeline search failed (falling back to ILIKE): %s", e, exc_info=True)

    # ── Lấy products từ DB ────────────────────────────────────────────────────
    if used_pipeline and ranked_asins:
        page_asins = ranked_asins[offset: offset + limit]
        if page_asins:
            products_map = {
                p.external_id: p
                for p in db.query(Product).filter(Product.external_id.in_(page_asins)).all()
            }
            items = [products_map[a] for a in page_asins if a in products_map]
            total = len(ranked_asins)
        else:
            items, total = [], len(ranked_asins)
    else:
        # Fallback: ILIKE
        items, total = _fallback_search(db, query, limit, offset)

    search_mode = "pipeline" if used_pipeline else "ilike"
    return ApiResponse(
        data=ProductSearchResponse(
            items=items,
            total=total,
            query=query,
            search_mode=search_mode,
            pipeline_error=pipeline_error,
            trace=search_trace if include_trace else None,
        ),
        message="Search successful",
        code=200,
    )


@router.post(
    "/evaluate-ranking",
    response_model=ApiResponse[RankingEvaluationResponse],
    summary="Đánh giá mức phù hợp của top ranking với xu hướng user",
    description=(
        "Dùng LLM để đánh giá top-k sản phẩm đầu bảng có hợp lý với lịch sử tương tác "
        "của user hiện tại hay không."
    ),
    responses={
        401: {"description": "Thiếu hoặc sai token"},
        422: {"description": "Payload không hợp lệ"},
    },
)
def evaluate_ranking(
    payload: RankingEvaluationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query_text = payload.query.strip()
    if not query_text:
        raise HTTPException(status_code=422, detail="Query is required")

    ranked_ids: list[int] = [pid for pid in payload.product_ids if isinstance(pid, int)]
    if not ranked_ids:
        raise HTTPException(status_code=422, detail="product_ids must not be empty")

    top_k = max(1, min(payload.top_k, 100))
    target_ids = ranked_ids[:top_k]

    products = db.query(Product).filter(Product.id.in_(target_ids)).all()
    product_map = {product.id: product for product in products}
    ordered_products = [product_map[pid] for pid in target_ids if pid in product_map]

    if not ordered_products:
        raise HTTPException(status_code=422, detail="No valid products found for evaluation")

    interactions = (
        db.query(Interaction, Product)
        .join(Product, Product.id == Interaction.product_id)
        .filter(Interaction.user_id == current_user.id)
        .order_by(Interaction.created_at.desc())
        .limit(200)
        .all()
    )

    interaction_count = len(interactions)
    purchase_count = sum(1 for interaction, _ in interactions if interaction.action_type == "purchase")
    brand_counter = Counter(
        product.brand.strip()
        for _, product in interactions
        if product.brand and product.brand.strip()
    )
    category_counter = Counter(
        product.category.strip()
        for _, product in interactions
        if product.category and product.category.strip()
    )
    top_brands = [name for name, _ in brand_counter.most_common(5)]
    top_categories = [name for name, _ in category_counter.most_common(5)]

    top_brand_set = {brand.lower() for brand in top_brands}
    top_category_set = {category.lower() for category in top_categories}
    brand_hit = sum(
        1
        for product in ordered_products
        if product.brand and product.brand.strip().lower() in top_brand_set
    )
    category_hit = sum(
        1
        for product in ordered_products
        if product.category and product.category.strip().lower() in top_category_set
    )
    evaluated_count = len(ordered_products)

    product_lines = []
    for index, product in enumerate(ordered_products, start=1):
        product_lines.append(
            f"{index}. title={product.title}; brand={product.brand}; category={product.category}; "
            f"price={product.price}"
        )

    llm_used = False
    query_fit_score = 0
    user_fit_score = 0
    overall_score = 0
    verdict = ""
    summary_text = ""
    strengths: list[str] = []
    risks: list[str] = []
    try:
        from offline.query_engine._llm_client import chat

        prompt = (
            "Bạn là evaluator cho ranking recommendation.\n"
            "Đánh giá mức hợp lý của top sản phẩm theo 2 chiều: (1) hợp query, (2) hợp user.\n"
            "Trả về JSON hợp lệ theo schema:\n"
            "{"
            "\"query_fit_score\": number(0-100), "
            "\"user_fit_score\": number(0-100), "
            "\"score\": number(0-100), "
            "\"verdict\": string, "
            "\"summary\": string, "
            "\"strengths\": string[], "
            "\"risks\": string[]"
            "}\n\n"
            "YÊU CẦU: Chỉ chấm bằng suy luận AI từ dữ liệu dưới đây, không dùng heuristic cứng.\n"
            f"Query: {query_text}\n"
            f"User interactions: {interaction_count}, purchases: {purchase_count}\n"
            f"Top brands from history: {top_brands}\n"
            f"Top categories from history: {top_categories}\n"
            f"Brand hit in top list: {brand_hit}/{evaluated_count}\n"
            f"Category hit in top list: {category_hit}/{evaluated_count}\n"
            f"Ranking candidates (ordered):\n" + "\n".join(product_lines)
        )
        llm_raw = chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=700,
            temperature=0.2,
        )
        llm_json = _extract_json_object(llm_raw)
        if not llm_json:
            raise RuntimeError("LLM did not return valid JSON")

        query_fit_score = max(0, min(100, int(llm_json["query_fit_score"])))
        user_fit_score = max(0, min(100, int(llm_json["user_fit_score"])))
        overall_score = max(0, min(100, int(llm_json["score"])))
        verdict = str(llm_json["verdict"])
        summary_text = str(llm_json["summary"])
        llm_strengths = llm_json.get("strengths")
        llm_risks = llm_json.get("risks")
        if isinstance(llm_strengths, list):
            strengths = [str(item) for item in llm_strengths[:5]]
        if isinstance(llm_risks, list):
            risks = [str(item) for item in llm_risks[:5]]
        llm_used = True
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"AI evaluation unavailable: {exc}",
        ) from exc

    return ApiResponse(
        data=RankingEvaluationResponse(
            query=query_text,
            evaluated_count=evaluated_count,
            query_fit_score=query_fit_score,
            user_fit_score=user_fit_score,
            score=overall_score,
            verdict=verdict,
            summary=summary_text,
            strengths=strengths[:5],
            risks=risks[:5],
            used_llm=llm_used,
        ),
        message="Ranking evaluation generated",
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
