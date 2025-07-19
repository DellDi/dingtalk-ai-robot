#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SSH服务API端点模块，用于远程服务器管理
"""

from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from app.services.ssh.client import SSHClient, SSHManager
from app.core.container import get_ssh_client_dependency

router = APIRouter()


class CommandRequest(BaseModel):
    """SSH命令执行请求模型"""
    host: str = Field(..., description="目标主机地址")
    command: str = Field(..., description="要执行的命令")
    username: Optional[str] = Field(None, description="SSH用户名，不提供则使用配置默认值")
    password: Optional[str] = Field(None, description="SSH密码，不提供则使用配置默认值")
    key_path: Optional[str] = Field(None, description="SSH密钥路径，不提供则使用配置默认值")
    port: int = Field(22, description="SSH端口")


class CommandResponse(BaseModel):
    """SSH命令执行响应模型"""
    success: bool
    message: str
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class FileTransferRequest(BaseModel):
    """文件传输请求模型"""
    host: str = Field(..., description="目标主机地址")
    local_path: str = Field(..., description="本地文件路径")
    remote_path: str = Field(..., description="远程文件路径")
    username: Optional[str] = Field(None, description="SSH用户名，不提供则使用配置默认值")
    password: Optional[str] = Field(None, description="SSH密码，不提供则使用配置默认值")
    key_path: Optional[str] = Field(None, description="SSH密钥路径，不提供则使用配置默认值")
    port: int = Field(22, description="SSH端口")
    direction: str = Field("upload", description="传输方向，upload或download")


class FileTransferResponse(BaseModel):
    """文件传输响应模型"""
    success: bool
    message: str


class BatchCommandRequest(BaseModel):
    """批量SSH命令执行请求模型"""
    hosts: List[str] = Field(..., description="目标主机地址列表")
    command: str = Field(..., description="要执行的命令")


class BatchCommandResponse(BaseModel):
    """批量SSH命令执行响应模型"""
    success: bool
    message: str
    results: Dict[str, Dict[str, Any]]


@router.post("/execute", response_model=CommandResponse)
async def execute_command(request: CommandRequest):
    """
    在远程服务器上执行命令（传统方式）
    """
    try:
        # 创建SSH客户端
        client = SSHClient(
            host=request.host,
            username=request.username,
            password=request.password,
            key_path=request.key_path,
            port=request.port
        )

        # 连接到服务器
        connected = await client.connect()
        if not connected:
            return CommandResponse(
                success=False,
                message=f"无法连接到主机 {request.host}"
            )

        # 执行命令
        exit_code, stdout, stderr = await client.execute_command(request.command)

        # 关闭连接
        client.close()

        # 返回结果
        if exit_code == 0:
            return CommandResponse(
                success=True,
                message="命令执行成功",
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr
            )
        else:
            return CommandResponse(
                success=False,
                message="命令执行失败",
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行命令异常: {str(e)}")


class SimpleCommandRequest(BaseModel):
    """简化的SSH命令执行请求模型（使用依赖注入）"""
    command: str = Field(..., description="要执行的命令")


@router.post("/execute-di", response_model=CommandResponse)
async def execute_command_with_di(
    request: SimpleCommandRequest,
    ssh_client: SSHClient = Depends(get_ssh_client_dependency)
):
    """
    在远程服务器上执行命令（使用依赖注入）

    这个端点演示了如何使用依赖注入来获取预配置的SSH客户端
    """
    try:
        # 连接到服务器（使用配置的默认主机）
        connected = await ssh_client.connect()
        if not connected:
            return CommandResponse(
                success=False,
                message=f"无法连接到默认主机"
            )

        # 执行命令
        exit_code, stdout, stderr = await ssh_client.execute_command(request.command)

        # 关闭连接
        ssh_client.close()

        # 返回结果
        if exit_code == 0:
            return CommandResponse(
                success=True,
                message="命令执行成功（依赖注入）",
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr
            )
        else:
            return CommandResponse(
                success=False,
                message="命令执行失败（依赖注入）",
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行命令异常: {str(e)}")


@router.post("/transfer", response_model=FileTransferResponse)
async def transfer_file(request: FileTransferRequest):
    """
    传输文件到/从远程服务器
    """
    try:
        # 创建SSH客户端
        client = SSHClient(
            host=request.host,
            username=request.username,
            password=request.password,
            key_path=request.key_path,
            port=request.port
        )

        # 连接到服务器
        connected = await client.connect()
        if not connected:
            return FileTransferResponse(
                success=False,
                message=f"无法连接到主机 {request.host}"
            )

        # 执行文件传输
        if request.direction.lower() == "upload":
            success = await client.upload_file(request.local_path, request.remote_path)
            operation = "上传"
        else:
            success = await client.download_file(request.remote_path, request.local_path)
            operation = "下载"

        # 关闭连接
        client.close()

        # 返回结果
        if success:
            return FileTransferResponse(
                success=True,
                message=f"文件{operation}成功"
            )
        else:
            return FileTransferResponse(
                success=False,
                message=f"文件{operation}失败"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件传输异常: {str(e)}")


@router.post("/batch_execute", response_model=BatchCommandResponse)
async def batch_execute_command(request: BatchCommandRequest):
    """
    在多个远程服务器上批量执行命令
    """
    try:
        # 创建SSH管理器
        manager = SSHManager()

        # 执行结果
        results = {}

        # 在每个主机上执行命令
        for host in request.hosts:
            # 获取SSH客户端
            client = await manager.get_client(host)
            if not client:
                results[host] = {
                    "success": False,
                    "message": f"无法连接到主机 {host}",
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"无法连接到主机 {host}"
                }
                continue

            # 执行命令
            exit_code, stdout, stderr = await client.execute_command(request.command)

            # 记录结果
            results[host] = {
                "success": exit_code == 0,
                "message": "命令执行成功" if exit_code == 0 else "命令执行失败",
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr
            }

        # 关闭所有连接
        manager.close_all()

        # 返回结果
        return BatchCommandResponse(
            success=True,
            message="批量命令执行完成",
            results=results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量执行命令异常: {str(e)}")


@router.post("/dify_upgrade")
async def upgrade_dify_service(
    hosts: List[str] = Body(..., description="目标主机地址列表"),
    version: Optional[str] = Body(None, description="要升级的版本，不提供则升级到最新版")
):
    """
    升级指定服务器上的Dify服务

    这是一个自定义的高级操作，会执行一系列命令来升级Dify服务
    """
    try:
        # 创建SSH管理器
        manager = SSHManager()

        # 升级结果
        results = {}

        # 在每个主机上执行升级
        for host in hosts:
            # 获取SSH客户端
            client = await manager.get_client(host)
            if not client:
                results[host] = {
                    "success": False,
                    "message": f"无法连接到主机 {host}"
                }
                continue

            # 构建升级命令
            # 这里是一个简化的示例，实际升级可能需要更复杂的步骤
            commands = [
                "cd /path/to/dify",
                "git pull",
            ]

            if version:
                commands.append(f"git checkout {version}")

            commands.extend([
                "docker-compose down",
                "docker-compose pull",
                "docker-compose up -d"
            ])

            command = " && ".join(commands)

            # 执行升级命令
            exit_code, stdout, stderr = await client.execute_command(command)

            # 记录结果
            results[host] = {
                "success": exit_code == 0,
                "message": "Dify服务升级成功" if exit_code == 0 else "Dify服务升级失败",
                "details": stdout if exit_code == 0 else stderr
            }

        # 关闭所有连接
        manager.close_all()

        # 返回结果
        return {
            "success": True,
            "message": "Dify服务升级操作完成",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"升级Dify服务异常: {str(e)}")
