from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.auth import AuthTokenResponse, LoginAsRequest, LoginRequest, RegisterRequest

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=ApiResponse[AuthTokenResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Đăng ký tài khoản",
    description="Tạo người dùng mới bằng email/password và trả về access token.",
    response_description="Thông tin token sau khi đăng ký thành công.",
    responses={
        409: {"description": "Email đã tồn tại"},
        422: {"description": "Dữ liệu đầu vào không hợp lệ"},
    },
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(str(user.id))
    return ApiResponse(
        data=AuthTokenResponse(
            access_token=token,
            user_id=user.id,
            email=user.email,
            external_user_id=user.external_user_id,
        ),
        message="Register successful",
        code=status.HTTP_201_CREATED,
    )


@router.post(
    "/login",
    response_model=ApiResponse[AuthTokenResponse],
    summary="Đăng nhập",
    description="Xác thực email/password và trả về access token.",
    response_description="Thông tin token sau khi đăng nhập thành công.",
    responses={
        401: {"description": "Sai email hoặc mật khẩu"},
        422: {"description": "Dữ liệu đầu vào không hợp lệ"},
    },
)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(str(user.id))
    return ApiResponse(
        data=AuthTokenResponse(
            access_token=token,
            user_id=user.id,
            email=user.email,
            external_user_id=user.external_user_id,
        ),
        message="Login successful",
        code=status.HTTP_200_OK,
    )


@router.post(
    "/login-as",
    response_model=ApiResponse[AuthTokenResponse],
    summary="Demo login (không cần password)",
    description="Đăng nhập bằng external_user_id (Amazon ID). Dùng cho demo — không yêu cầu password.",
    responses={
        404: {"description": "Không tìm thấy user"},
    },
)
def login_as(payload: LoginAsRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.external_user_id == payload.external_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = create_access_token(str(user.id))
    return ApiResponse(
        data=AuthTokenResponse(
            access_token=token,
            user_id=user.id,
            email=user.email,
            external_user_id=user.external_user_id,
        ),
        message="Login successful",
        code=status.HTTP_200_OK,
    )
