# !/usr/bin/env python

import argparse
import logging
from dingtalk_stream import AckMessage
import dingtalk_stream
from alibabacloud_dingtalk.oauth2_1_0.client import Client as dingtalkoauth2_1_0Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dingtalk.oauth2_1_0 import models as dingtalkoauth_2__1__0_models
from alibabacloud_dingtalk.robot_1_0.client import Client as dingtalkrobot_1_0Client
from alibabacloud_dingtalk.robot_1_0 import models as dingtalkrobot__1__0_models
from alibabacloud_tea_util import models as util_models
import time

_token_cache = {"token": None, "expire": 0}

def setup_logger():
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter('%(asctime)s %(name)-8s %(levelname)-8s %(message)s [%(filename)s:%(lineno)d]'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def define_options():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--client_id', dest='client_id', required=True,
        help='app_key or suite_key from https://open-dev.digntalk.com'
    )
    parser.add_argument(
        '--client_secret', dest='client_secret', required=True,
        help='app_secret or suite_secret from https://open-dev.digntalk.com'
    )
    parser.add_argument(
        '--robot_code', dest='robot_code', required=True,
        help='robot_code from https://open-dev.dingtalk.com'
    )
    options = parser.parse_args()
    return options


def get_token(options):
    """
    使用钉钉SDK获取access_token，带本地缓存，2小时有效，提前200秒刷新。
    :param options: 命令行参数对象，包含 client_id, client_secret
    :return: access_token字符串，获取失败返回None
    """
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expire"]:
        return _token_cache["token"]
    config = open_api_models.Config()
    config.protocol = 'https'
    config.region_id = 'central'
    client = dingtalkoauth2_1_0Client(config)
    get_access_token_request = dingtalkoauth_2__1__0_models.GetAccessTokenRequest(
        app_key=options.client_id,
        app_secret=options.client_secret
    )
    try:
        response = client.get_access_token(get_access_token_request)
        token = getattr(response.body, "access_token", None)
        expire_in = getattr(response.body, "expire_in", 7200)
        if token:
            _token_cache["token"] = token
            _token_cache["expire"] = now + expire_in - 200  # 提前200秒刷新
        return token
    except Exception as err:
        print(f"获取token失败: {err}")
        return None


def send_robot_group_message(access_token, open_conversation_id, options):
    """
    使用钉钉SDK发送群消息
    :param access_token: 已获取的 access_token
    :param open_conversation_id: 群会话ID
    :param options: 命令行参数对象，包含 robot_code
    :return: 发送结果或 None
    """
    robot_code = options.robot_code
    msg_param = '{"content":"python-getting-start say：hello"}'
    msg_key = 'sampleText'
    config = open_api_models.Config()
    config.protocol = 'https'
    config.region_id = 'central'
    client = dingtalkrobot_1_0Client(config)
    org_group_send_headers = dingtalkrobot__1__0_models.OrgGroupSendHeaders()
    org_group_send_headers.x_acs_dingtalk_access_token = access_token
    org_group_send_request = dingtalkrobot__1__0_models.OrgGroupSendRequest(
        msg_param=msg_param,
        msg_key=msg_key,
        open_conversation_id=open_conversation_id,
        robot_code=robot_code
    )
    try:
        response = client.org_group_send_with_options(
            org_group_send_request,
            org_group_send_headers,
            util_models.RuntimeOptions()
        )
        print("消息发送成功，返回：", response)
        return response
    except Exception as err:
        print(f"发送群消息失败: {err}")
        return None


class EchoTextHandler(dingtalk_stream.ChatbotHandler):
    def __init__(self, logger: logging.Logger = None, options=None):
        super(dingtalk_stream.ChatbotHandler, self).__init__()
        self.logger = logger
        self.options = options

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
        open_conversation_id = incoming_message.conversation_id
        access_token = get_token(self.options)
        if access_token:
            send_robot_group_message(access_token, open_conversation_id, self.options)
        else:
            print("access_token 获取失败")
        return AckMessage.STATUS_OK, 'OK'


def main():
    logger = setup_logger()
    options = define_options()
    credential = dingtalk_stream.Credential(options.client_id, options.client_secret)
    client = dingtalk_stream.DingTalkStreamClient(credential)
    client.register_callback_handler(
        dingtalk_stream.chatbot.ChatbotMessage.TOPIC,
        EchoTextHandler(logger, options)
    )
    client.start_forever()


if __name__ == '__main__':
    main()