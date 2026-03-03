from datetime import datetime

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
