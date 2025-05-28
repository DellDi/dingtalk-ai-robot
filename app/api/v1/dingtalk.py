#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
钉钉API端点模块
"""

from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.dingtalk_client import DingTalkClient
from app.services.dingtalk.card import send_action_card, send_feed_card

router = APIRouter()


class MessageRequest(BaseModel):
    """消息请求模型"""
    conversation_id: str = Field(..., description="会话ID")
    content: str = Field(..., description="消息内容")
    msg_type: str = Field("sampleText", description="消息类型")


class MessageResponse(BaseModel):
    """消息响应模型"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class CardButton(BaseModel):
    """卡片按钮模型"""
    title: str = Field(..., description="按钮标题")
    url: str = Field(..., description="按钮链接")


class ActionCardRequest(BaseModel):
    """交互式卡片请求模型"""
    conversation_id: str = Field(..., description="会话ID")
    title: str = Field(..., description="卡片标题")
    content: str = Field(..., description="卡片内容，支持markdown格式")
    btns: List[CardButton] = Field(..., description="按钮列表")
    btn_orientation: str = Field("0", description="按钮排列方向，0：横向排列，1：纵向排列")


class FeedCardItem(BaseModel):
    """图文卡片项模型"""
    title: str = Field(..., description="标题")
    message_url: str = Field(..., description="消息链接")
    pic_url: str = Field(..., description="图片链接")


class FeedCardRequest(BaseModel):
    """图文卡片列表请求模型"""
    conversation_id: str = Field(..., description="会话ID")
    links: List[FeedCardItem] = Field(..., description="链接列表")


@router.post("/send_message", response_model=MessageResponse)
async def send_message(request: MessageRequest):
    """
    发送普通消息到钉钉群聊
    """
    try:
        client = DingTalkClient()
        result = client.send_group_message(
            conversation_id=request.conversation_id,
            message=request.content,
            msg_type=request.msg_type
        )
        
        if result:
            return MessageResponse(
                success=True,
                message="消息发送成功",
                data={"request_id": getattr(result.body, "request_id", "")}
            )
        else:
            return MessageResponse(
                success=False,
                message="消息发送失败"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送消息异常: {str(e)}")


@router.post("/send_action_card", response_model=MessageResponse)
async def send_action_card_api(request: ActionCardRequest):
    """
    发送交互式卡片消息到钉钉群聊
    """
    try:
        # 转换按钮格式
        btns = [{"title": btn.title, "url": btn.url} for btn in request.btns]
        
        # 发送卡片消息
        success = await send_action_card(
            conversation_id=request.conversation_id,
            title=request.title,
            content=request.content,
            btns=btns,
            btn_orientation=request.btn_orientation
        )
        
        if success:
            return MessageResponse(
                success=True,
                message="交互式卡片消息发送成功"
            )
        else:
            return MessageResponse(
                success=False,
                message="交互式卡片消息发送失败"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送卡片消息异常: {str(e)}")


@router.post("/send_feed_card", response_model=MessageResponse)
async def send_feed_card_api(request: FeedCardRequest):
    """
    发送图文卡片列表消息到钉钉群聊
    """
    try:
        # 转换链接格式
        links = [
            {
                "title": item.title,
                "messageURL": item.message_url,
                "picURL": item.pic_url
            }
            for item in request.links
        ]
        
        # 发送图文卡片消息
        success = await send_feed_card(
            conversation_id=request.conversation_id,
            links=links
        )
        
        if success:
            return MessageResponse(
                success=True,
                message="图文卡片列表消息发送成功"
            )
        else:
            return MessageResponse(
                success=False,
                message="图文卡片列表消息发送失败"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送图文卡片消息异常: {str(e)}")
