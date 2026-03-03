from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProductResponse(BaseModel):
    id: int = Field(description="ID nội bộ của sản phẩm")
    external_id: str | None = Field(default=None, description="ID gốc từ nguồn dữ liệu bên ngoài")
    title: str = Field(description="Tên sản phẩm")
    brand: str | None = Field(default=None, description="Thương hiệu")
    description: str | None = Field(default=None, description="Mô tả sản phẩm")
    category: str | None = Field(default=None, description="Danh mục")
    price: float | None = Field(default=None, description="Giá sản phẩm")
    image_url: str | None = Field(default=None, description="URL ảnh sản phẩm")
    created_at: datetime = Field(description="Thời điểm tạo bản ghi")

    model_config = {"from_attributes": True}


class ProductSearchResponse(BaseModel):
    items: list[ProductResponse] = Field(description="Danh sách sản phẩm tìm thấy")
    total: int = Field(description="Tổng số sản phẩm phù hợp")
    query: str = Field(description="Từ khóa tìm kiếm")
    search_mode: str = Field(
        default="ilike",
        description="Mode tìm kiếm đã dùng: 'pipeline' (KG+KGAT) hoặc 'ilike' (DB fallback)",
    )
    pipeline_error: str | None = Field(
        default=None,
        description="Lỗi pipeline nếu có (chỉ hiển thị khi fallback về ilike)",
    )
    trace: dict[str, Any] | None = Field(
        default=None,
        description="Trace các bước xử lý tìm kiếm (intent/cypher/candidates/rerank).",
    )


class RankingEvaluationRequest(BaseModel):
    query: str = Field(description="Query tìm kiếm gốc của người dùng")
    product_ids: list[int] = Field(description="Danh sách product ids theo thứ tự ranking")
    top_k: int = Field(default=40, ge=1, le=100, description="Số lượng sản phẩm đầu bảng cần evaluate")


class RankingEvaluationResponse(BaseModel):
    query: str
    evaluated_count: int
    query_fit_score: int = Field(default=0, description="Điểm phù hợp với query 0-100")
    user_fit_score: int = Field(default=0, description="Điểm phù hợp với xu hướng user 0-100")
    score: int = Field(description="Điểm tổng hợp 0-100 so với xu hướng user")
    verdict: str = Field(description="Kết luận ngắn về độ hợp lý của ranking")
    summary: str = Field(description="Phân tích tổng hợp từ LLM")
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    used_llm: bool = Field(default=False, description="Cho biết có dùng LLM thành công hay fallback")
