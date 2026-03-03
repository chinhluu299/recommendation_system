from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr = Field(description="Email đăng ký tài khoản")
    password: str = Field(min_length=6, max_length=128, description="Mật khẩu từ 6 đến 128 ký tự")
    full_name: str | None = Field(default=None, description="Tên hiển thị của người dùng")

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "alice@example.com",
                "password": "123456",
                "full_name": "Alice Nguyen",
            }
        }
    }


class LoginRequest(BaseModel):
    email: EmailStr = Field(description="Email đã đăng ký")
    password: str = Field(description="Mật khẩu")

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "alice@example.com",
                "password": "123456",
            }
        }
    }


class LoginAsRequest(BaseModel):
    """Demo login: đăng nhập bằng external_user_id, không cần password."""
    external_user_id: str = Field(description="Amazon user ID từ dataset")

    model_config = {
        "json_schema_extra": {
            "example": {"external_user_id": "AHATA6X6MYTC3VNBFJ3WIYVK257A"}
        }
    }


class AuthTokenResponse(BaseModel):
    access_token: str = Field(description="JWT access token")
    token_type: str = Field(default="bearer", description="Loại token")
    user_id: int = Field(description="ID người dùng")
    email: str | None = Field(default=None, description="Email người dùng")
    external_user_id: str | None = Field(default=None, description="Amazon user ID")
