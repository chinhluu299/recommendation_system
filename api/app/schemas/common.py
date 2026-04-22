from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    data: T | None = Field(default=None, description="Dữ liệu trả về, null nếu request lỗi")
    message: str = Field(default="Success", description="Thông điệp mô tả kết quả xử lý")
    code: int = Field(default=200, description="Mã trạng thái nghiệp vụ, thường trùng HTTP status")
