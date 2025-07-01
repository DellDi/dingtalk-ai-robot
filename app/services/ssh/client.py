#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SSH远程连接服务模块，用于远程管理服务器
"""

import os
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union

import paramiko
from loguru import logger

from app.core.config import settings


class SSHClient:
    """SSH客户端，用于远程连接和管理服务器"""
    
    def __init__(
        self, 
        host: str, 
        username: str = None, 
        password: str = None, 
        key_path: str = None, 
        port: int = 22
    ):
        """
        初始化SSH客户端
        
        Args:
            host: 服务器主机地址
            username: SSH用户名，如果为None则使用配置中的默认值
            password: SSH密码，如果为None则使用配置中的默认值
            key_path: SSH密钥路径，如果为None则使用配置中的默认值
            port: SSH端口，默认为22
        """
        self.host = host
        self.username = username or settings.SSH_USERNAME
        self.password = password or settings.SSH_PASSWORD
        self.key_path = key_path or settings.SSH_KEY_PATH
        self.port = port
        self.client = None
        
    async def connect(self) -> bool:
        """
        连接到SSH服务器
        
        Returns:
            bool: 是否连接成功
        """
        try:
            logger.info(f"连接到SSH服务器: {self.host}")
            
            # 创建SSH客户端
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 优先使用密钥连接
            if self.key_path and os.path.exists(os.path.expanduser(self.key_path)):
                key = paramiko.RSAKey.from_private_key_file(os.path.expanduser(self.key_path))
                
                # 使用run_in_executor在线程池中执行阻塞操作
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.client.connect(
                        hostname=self.host,
                        port=self.port,
                        username=self.username,
                        pkey=key,
                        timeout=10
                    )
                )
            # 如果没有密钥或密钥连接失败，尝试使用密码连接
            elif self.password:
                # 使用run_in_executor在线程池中执行阻塞操作
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.client.connect(
                        hostname=self.host,
                        port=self.port,
                        username=self.username,
                        password=self.password,
                        timeout=10
                    )
                )
            else:
                logger.error(f"SSH连接失败: 未提供密钥或密码")
                return False
            
            logger.info(f"SSH连接成功: {self.host}")
            return True
            
        except Exception as e:
            logger.error(f"SSH连接异常: {e}")
            if self.client:
                self.client.close()
                self.client = None
            return False
    
    async def execute_command(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        """
        执行SSH命令
        
        Args:
            command: 要执行的命令
            timeout: 命令执行超时时间（秒）
            
        Returns:
            Tuple[int, str, str]: 退出码、标准输出和标准错误
        """
        if not self.client:
            connected = await self.connect()
            if not connected:
                return -1, "", "SSH连接失败"
        
        try:
            logger.info(f"[SSH-DEBUG] 在 {self.host} 上执行命令: {command}")
            logger.info(f"[SSH-DEBUG] 命令超时设置: {timeout}秒")
            
            # 检测可能有问题的命令类型
            interactive_commands = ['top', 'htop', 'vi', 'vim', 'nano', 'less', 'more', 'tail -f']
            is_interactive = any(cmd in command.lower() for cmd in interactive_commands)
            if is_interactive:
                logger.warning(f"[SSH-DEBUG] 检测到交互式命令: {command}")
            
            # 使用run_in_executor在线程池中执行阻塞操作
            loop = asyncio.get_event_loop()
            
            logger.info(f"[SSH-DEBUG] 开始执行命令...")
            # 执行命令
            stdin, stdout, stderr = await loop.run_in_executor(
                None,
                lambda: self.client.exec_command(command, timeout=timeout)
            )
            
            logger.info(f"[SSH-DEBUG] 命令已提交，等待退出状态...")
            
            # 使用asyncio.wait_for添加超时控制
            try:
                # 获取命令输出
                exit_code = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: stdout.channel.recv_exit_status()
                    ),
                    timeout=timeout
                )
                logger.info(f"[SSH-DEBUG] 获取到退出状态: {exit_code}")
                
            except asyncio.TimeoutError:
                logger.error(f"[SSH-DEBUG] 命令执行超时 ({timeout}秒)，可能是交互式命令或长时间运行命令")
                # 尝试强制关闭通道
                try:
                    stdout.channel.close()
                    stderr.channel.close()
                except:
                    pass
                return -2, "", f"命令执行超时 ({timeout}秒) - 可能是交互式命令或需要更长执行时间"
            
            logger.info(f"[SSH-DEBUG] 开始读取输出...")
            stdout_str = await loop.run_in_executor(
                None,
                lambda: stdout.read().decode('utf-8')
            )
            
            stderr_str = await loop.run_in_executor(
                None,
                lambda: stderr.read().decode('utf-8')
            )
            
            logger.info(f"[SSH-DEBUG] 命令执行完成，退出码: {exit_code}")
            logger.info(f"[SSH-DEBUG] 标准输出长度: {len(stdout_str)} 字符")
            logger.info(f"[SSH-DEBUG] 标准错误长度: {len(stderr_str)} 字符")
            
            if exit_code != 0:
                logger.warning(f"[SSH-DEBUG] 命令执行异常: {stderr_str}")
                
            return exit_code, stdout_str, stderr_str
            
        except Exception as e:
            logger.error(f"[SSH-DEBUG] 执行命令异常: {e}")
            return -1, "", str(e)
        
    async def upload_file(self, local_path: str, remote_path: str) -> bool:
        """
        上传文件到远程服务器
        
        Args:
            local_path: 本地文件路径
            remote_path: 远程文件路径
            
        Returns:
            bool: 是否上传成功
        """
        if not self.client:
            connected = await self.connect()
            if not connected:
                return False
        
        try:
            logger.info(f"上传文件 {local_path} 到 {self.host}:{remote_path}")
            
            # 使用run_in_executor在线程池中执行阻塞操作
            loop = asyncio.get_event_loop()
            
            # 创建SFTP客户端
            sftp = await loop.run_in_executor(
                None,
                lambda: self.client.open_sftp()
            )
            
            # 上传文件
            await loop.run_in_executor(
                None,
                lambda: sftp.put(local_path, remote_path)
            )
            
            # 关闭SFTP客户端
            await loop.run_in_executor(
                None,
                lambda: sftp.close()
            )
            
            logger.info(f"文件上传成功")
            return True
            
        except Exception as e:
            logger.error(f"上传文件异常: {e}")
            return False
    
    async def download_file(self, remote_path: str, local_path: str) -> bool:
        """
        从远程服务器下载文件
        
        Args:
            remote_path: 远程文件路径
            local_path: 本地文件路径
            
        Returns:
            bool: 是否下载成功
        """
        if not self.client:
            connected = await self.connect()
            if not connected:
                return False
        
        try:
            logger.info(f"从 {self.host}:{remote_path} 下载文件到 {local_path}")
            
            # 使用run_in_executor在线程池中执行阻塞操作
            loop = asyncio.get_event_loop()
            
            # 创建SFTP客户端
            sftp = await loop.run_in_executor(
                None,
                lambda: self.client.open_sftp()
            )
            
            # 下载文件
            await loop.run_in_executor(
                None,
                lambda: sftp.get(remote_path, local_path)
            )
            
            # 关闭SFTP客户端
            await loop.run_in_executor(
                None,
                lambda: sftp.close()
            )
            
            logger.info(f"文件下载成功")
            return True
            
        except Exception as e:
            logger.error(f"下载文件异常: {e}")
            return False
    
    def close(self):
        """关闭SSH连接"""
        if self.client:
            try:
                self.client.close()
                logger.info(f"SSH连接已关闭: {self.host}")
            except Exception as e:
                logger.error(f"关闭SSH连接异常: {e}")
            finally:
                self.client = None


class SSHManager:
    """SSH管理器，用于管理多个SSH连接"""
    
    def __init__(self):
        """初始化SSH管理器"""
        self.hosts = self._parse_hosts()
        self.clients = {}
        
    def _parse_hosts(self) -> List[str]:
        """解析配置的主机列表"""
        if not settings.SSH_HOSTS:
            return []
        
        return [host.strip() for host in settings.SSH_HOSTS.split(",") if host.strip()]
    
    async def get_client(self, host: str) -> Optional[SSHClient]:
        """
        获取指定主机的SSH客户端
        
        Args:
            host: 主机地址
            
        Returns:
            Optional[SSHClient]: SSH客户端实例，如果不存在则返回None
        """
        if host not in self.clients:
            client = SSHClient(host)
            connected = await client.connect()
            if connected:
                self.clients[host] = client
            else:
                return None
        
        return self.clients.get(host)
    
    async def execute_on_all(self, command: str) -> Dict[str, Tuple[int, str, str]]:
        """
        在所有主机上执行命令
        
        Args:
            command: 要执行的命令
            
        Returns:
            Dict[str, Tuple[int, str, str]]: 主机地址到执行结果的映射
        """
        results = {}
        
        for host in self.hosts:
            client = await self.get_client(host)
            if client:
                result = await client.execute_command(command)
                results[host] = result
            else:
                results[host] = (-1, "", f"无法连接到主机 {host}")
        
        return results
    
    def close_all(self):
        """关闭所有SSH连接"""
        for host, client in self.clients.items():
            client.close()
        
        self.clients = {}
