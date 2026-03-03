from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: int
    email: str | None
    external_user_id: str | None
    full_name: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserSummary(BaseModel):
    """User tóm tắt cho màn hình chọn user khi demo."""
    id: int
    external_user_id: str | None
    full_name: str | None
    interaction_count: int

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserSummary]
    total: int


class UserInteractedProduct(BaseModel):
    product_id: int
    title: str
    brand: str | None
    price: float | None
    image_url: str | None
    last_action_type: str
    last_interacted_at: datetime
    interaction_count: int
    purchase_count: int


class UserInteractionsResponse(BaseModel):
    items: list[UserInteractedProduct]
    total: int


class UserTrendInsightRequest(BaseModel):
    query: str
    lookback_limit: int = 120


class UserTrendInsightResponse(BaseModel):
    query: str
    insight: str
    interaction_count: int
    purchase_count: int
    top_brands: list[str]
    top_categories: list[str]
