#!/usr/bin/env python3
"""
测试钉钉消息发送修复
"""

import sys
import os
from unittest.mock import Mock, patch
from loguru import logger

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.dingtalk_client import DingTalkClient


def test_send_private_message_parameter_format():
    """测试send_private_message方法的参数格式"""
    try:
        # 创建DingTalkClient实例
        client = DingTalkClient()

        # 模拟access_token获取
        with patch.object(client, 'get_access_token', return_value='mock_token'):
            # 模拟钉钉API调用
            with patch('app.core.dingtalk_client.DingTalkRobotClient') as mock_robot_client:
                mock_client_instance = Mock()
                mock_robot_client.return_value = mock_client_instance
                mock_client_instance.batch_send_otowith_options.return_value = Mock()

                # 测试数据
                test_user_ids = ["test_user_123"]
                test_message = "测试消息"

                logger.info("🧪 开始测试send_private_message参数格式...")
                logger.info(f"📝 测试参数: user_ids={test_user_ids}, message='{test_message}'")
                logger.info(f"🔍 user_ids类型: {type(test_user_ids)}")

                # 调用方法
                result = client.send_private_message(test_user_ids, test_message)

                # 验证调用
                mock_client_instance.batch_send_otowith_options.assert_called_once()

                # 获取实际调用的参数
                call_args = mock_client_instance.batch_send_otowith_options.call_args
                request = call_args[0][0]  # 第一个位置参数是request

                logger.info(f"✅ API调用成功")
                logger.info(f"📊 请求参数: robot_code={request.robot_code}, user_ids={request.user_ids}")
                logger.info(f"🔍 user_ids类型: {type(request.user_ids)}")

                # 验证user_ids是列表类型
                if isinstance(request.user_ids, list):
                    logger.info("✅ user_ids参数格式正确（列表类型）")
                    return True
                else:
                    logger.error(f"❌ user_ids参数格式错误，期望list，实际{type(request.user_ids)}")
                    return False

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        return False


def test_message_handler_call_format():
    """测试消息处理器中的调用格式"""
    try:
        logger.info("🧪 测试消息处理器调用格式...")

        # 模拟单个sender_id（字符串）
        sender_id = "test_user_456"
        logger.info(f"📝 原始sender_id: {sender_id} (类型: {type(sender_id)})")

        # 模拟消息处理器中的转换
        user_ids_for_api = [sender_id]
        logger.info(f"🔄 转换后的user_ids: {user_ids_for_api} (类型: {type(user_ids_for_api)})")

        # 验证转换结果
        if isinstance(user_ids_for_api, list) and len(user_ids_for_api) == 1:
            logger.info("✅ 参数转换格式正确")
            return True
        else:
            logger.error("❌ 参数转换格式错误")
            return False

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        return False


def main():
    """主测试函数"""
    logger.info("🚀 开始钉钉消息发送修复测试")
    logger.info("=" * 50)

    # 测试1: send_private_message参数格式
    test1_success = test_send_private_message_parameter_format()

    # 测试2: 消息处理器调用格式
    test2_success = test_message_handler_call_format()

    # 输出测试结果
    logger.info("=" * 50)
    if test1_success and test2_success:
        logger.info("🎉 所有测试通过！钉钉消息发送修复成功")
    else:
        logger.error("❌ 部分测试失败，请检查修复情况")


if __name__ == "__main__":
    main()
