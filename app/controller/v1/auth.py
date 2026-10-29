from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.service.auth_service import CurrentUser, get_current_user, login_with_wechat, logout
from app.utils.response import success

router = APIRouter(prefix="/auth", tags=["auth"])


class WechatLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)


@router.post("/wechat-login")
def wechat_login(body: WechatLoginRequest, request: Request, db: Session = Depends(get_db)):
    return success(login_with_wechat(db, body.code), "登录成功", request)


@router.get("/userinfo")
def userinfo(request: Request, current_user: CurrentUser = Depends(get_current_user)):
    return success({"user_id": current_user.user_id, "role": current_user.role}, request=request)


@router.post("/logout")
def logout_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    logout(db, current_user)
    return success(message="已退出登录", request=request)
