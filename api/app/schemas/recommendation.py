from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    user_id: int = Field(description="ID người dùng cần gợi ý")
    query: str = Field(description="Ngữ cảnh/từ khóa tìm kiếm hiện tại của người dùng")
    limit: int = Field(default=10, ge=1, le=100, description="Số lượng sản phẩm gợi ý tối đa")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": 1,
                "query": "iphone 14 pro",
                "limit": 10,
            }
        }
    }


class RecommendationItem(BaseModel):
    product_id: int = Field(description="ID sản phẩm được gợi ý")
    score: float | None = Field(default=None, description="Điểm phù hợp (nếu có)")


class RecommendationResponse(BaseModel):
    user_id: int = Field(description="ID người dùng")
    query: str = Field(description="Query đầu vào")
    items: list[RecommendationItem] = Field(description="Danh sách sản phẩm gợi ý")
