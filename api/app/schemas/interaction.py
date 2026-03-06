from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class InteractionCreateRequest(BaseModel):
    user_id: int = Field(description="ID người dùng thực hiện hành vi")
    product_id: int = Field(description="ID sản phẩm được tương tác")
    action_type: Literal["view", "purchase"] = Field(description="Loại hành vi: view hoặc purchase")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": 1,
                "product_id": 101,
                "action_type": "view",
            }
        }
    }


class InteractionResponse(BaseModel):
    id: int = Field(description="ID bản ghi hành vi")
    user_id: int = Field(description="ID người dùng")
    product_id: int = Field(description="ID sản phẩm")
    action_type: str = Field(description="Loại hành vi")
    created_at: datetime = Field(description="Thời điểm ghi nhận")

    model_config = {"from_attributes": True}
