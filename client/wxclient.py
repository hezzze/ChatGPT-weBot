# -*- coding: utf-8 -*-
import json
import time
import re
import websocket
import asyncio
import requests

from bing.EdgeGPT import Chatbot as BingBot
from revChatGPT.V3 import Chatbot as ChatGPTbot

from client.lib.task import *
from client.lib.threads import *

import xml.etree.ElementTree as ET

from client.lib.local_config import local_config

# config
with open(".config/config.json", encoding="utf-8") as f:
    config = json.load(f)
f.close()

server_host = config["server_host"]
autoReply = config["autoReply"]
groupChatKey = config["groupChatKey"]
groupReplyMode = config["groupReplyMode"]
privateChatKey = config["privateChatKey"]
privateReplyMode = config["privateReplyMode"]
helpKey = config["helpKey"]
resetChatKey = config["resetChatKey"]
regenerateKey = config["regenerateKey"]
rollbackKey = config["rollbackKey"]
enableBingChat = config["enableBingChat"]
enableGPT4 = config["enableGPT4"]
sdImgKey = config["sdImgKey"]
sdNegativePromptKey = config["sdNegativePromptKey"]
midImgKey = config["midImgKey"]
midParamKey = config["midParamKey"]

# data
chatbots = dict()
global_context = {}
room_replies = dict()

# threads
global_thread = []

loop = asyncio.get_event_loop()


def getid():
    id = time.strftime("%Y%m%d%H%M%S", time.localtime(time.time()))
    return id


def get_chat_nick_p(wx_id, room_id):
    qs = {
        "id": getid(),
        "type": CHATROOM_MEMBER_NICK,
        "wxid": wx_id,
        "roomid": room_id,
        "content": "",
        "nickname": "",
        "ext": "",
    }
    s = json.dumps(qs)
    return s


def debug_switch():
    qs = {
        "id": getid(),
        "type": DEBUG_SWITCH,
        "content": "off",
        "wxid": "",
    }
    s = json.dumps(qs)
    return s


def handle_nick_test(j):
    data = json.loads(j["content"])
    print("测试群成员昵称：" + data["nick"])
    return data["nick"]


def handle_nick(j):
    # print("handle_nick:", j)
    data = json.loads(j["content"])
    wx_id = data["wxid"]
    room_id = data["roomid"]

    ws.send(
        send_at_meg(
            wx_id=wx_id,
            room_id=room_id,
            # pop the first reply in the list
            content=room_replies[(wx_id, room_id)].pop(0),
            nickname=data["nick"],
        )
    )

    # clear memory
    if len(room_replies[(wx_id, room_id)]) == 0:
        room_replies.pop((wx_id, room_id), None)


def hanle_memberlist(j):
    data = j["content"]
    print(data)
    # for d in data:
    #     print(d["room_id"])


def get_chatroom_memberlist():
    qs = {
        "id": getid(),
        "type": CHATROOM_MEMBER,
        "wxid": "",
        "roomid": "",
        "content": "",
        "nickname": "",
        "ext": "",
    }
    s = json.dumps(qs)
    return s


def send_at_meg(wx_id, room_id, content, nickname):
    qs = {
        "id": getid(),
        "type": AT_MSG,
        "wxid": wx_id,
        "roomid": room_id,
        "content": content,
        "nickname": nickname,
        "ext": "",
    }
    s = json.dumps(qs)
    return s


def destroy_all():
    qs = {
        "id": getid(),
        "type": DESTROY_ALL,
        "content": "none",
        "wxid": "node",
    }
    s = json.dumps(qs)
    return s


def send_pic_msg():
    qs = {
        "id": getid(),
        "type": PIC_MSG,
        "content": ".jpg",
        "wxid": "获取的wxid",
    }
    s = json.dumps(qs)
    return s


def get_personal_info():
    qs = {
        "id": getid(),
        "type": PERSONAL_INFO,
        "wxid": "ROOT",
        "roomid": "",
        "content": "",
        "nickname": "",
        "ext": "",
    }
    s = json.dumps(qs)
    return s


def get_personal_detail(wx_id):
    qs = {
        "id": getid(),
        "type": PERSONAL_DETAIL,
        "wxid": wx_id,
        "roomid": "",
        "content": "",
        "nickname": "",
        "ext": "",
    }
    s = json.dumps(qs)
    return s


def send_txt_msg(text_string, wx_id):
    qs = {
        "id": getid(),
        "type": TXT_MSG,
        "wxid": wx_id,
        "roomid": "",
        "content": text_string,  # 文本消息内容
        "nickname": "",
        "ext": "",
    }
    s = json.dumps(qs)
    return s


def send_wxuser_list():
    qs = {
        "id": getid(),
        "type": USER_LIST,
        "wxid": "",
        "roomid": "",
        "content": "",
        "nickname": "",
        "ext": "",
    }
    s = json.dumps(qs)
    return s


def handle_wxuser_list(j):
    content = j["content"]
    i = 0
    # 微信群
    for item in content:
        i += 1
        id = item["wxid"]
        m = id.find("@")
        if m != -1:
            print(i, "群聊", id, item["name"])

    # 微信其他好友，公众号等
    for item in content:
        i += 1
        id = item["wxid"]
        m = id.find("@")
        if m == -1:
            print(i, "个体", id, item["name"], item["wxcode"])


def translate(content, api_key=local_config["api_key"], proxy=local_config["proxy"]):
    session = requests.Session()
    proxies = {
        "http": proxy,
        "https": proxy,
    }
    session.proxies.update(proxies)

    response = session.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": "Bearer " + api_key},
        json={
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "user",
                    "content": f"translate '{content}' to english, reply only translation, if already english just echo back",
                }
            ],
            # kwargs
            "temperature": 0.7,
            "top_p": 1,
            "n": 1,
        },
        stream=False,
    )

    if response.status_code != 200:
        raise Exception(
            f"Error: {response.status_code} {response.reason} {response.text}",
        )

    resp = json.loads(response.content)
    return resp["choices"][0]["message"]["content"]


def handle_recv_txt_msg(j):
    print(j)

    wx_id = j["wxid"]
    room_id = ""
    content: str = j["content"]

    is_mention = re.search("@" + global_context["wx_name"], content) != None

    print("is mention: ", is_mention)

    is_room: bool
    is_ask: bool = False

    # chatbot: ChatGPTbot

    if len(wx_id) < 9 or wx_id[-9] != "@":
        is_room = False
        wx_id: str = j["wxid"]
        chatbot = chatbots.get((wx_id, ""))

        if content.startswith(privateChatKey):
            is_ask = True
            content = re.sub(privateChatKey, "", content)

    else:
        is_room = True
        wx_id = j["id1"]
        room_id = j["wxid"]
        chatbot = chatbots.get((wx_id, room_id))

        if content.startswith(groupChatKey):
            is_ask = True
            content = re.sub("@\S+\s+", "", content)

    if (not is_room or (is_room and is_mention)) and content.startswith(enableBingChat):
        # chatbot = BingBot(cookiePath="./.config/bing_cookies.json")
        # if is_room:
        #     chatbots.pop((wx_id, room_id), None)
        #     chatbots[(wx_id, room_id)] = chatbot
        # else:
        #     chatbots.pop((wx_id, ""), None)
        #     chatbots[(wx_id, "")] = chatbot

        # __reply(wx_id, room_id, "⚠️系统消息⚠️\n 切换到 Bing chat...", is_room)
        __reply(wx_id, room_id, f"⚠️系统消息⚠️\n该模式暂不可用({enableBingChat})", is_room)

    elif (not is_room or (is_room and is_mention)) and content.startswith(enableGPT4):
        # chatbot = ChatGPTbot(
        #     api_key=local_config["api_key"], proxy=local_config["proxy"], engine="gpt-4"
        # )
        # if is_room:
        #     chatbots.pop((wx_id, room_id), None)
        #     chatbots[(wx_id, room_id)] = chatbot
        # else:
        #     chatbots.pop((wx_id, ""), None)
        #     chatbots[(wx_id, "")] = chatbot

        # __reply(wx_id, room_id, "⚠️系统消息⚠️\n切换到 GPT4 测试模式...", is_room)
        __reply(wx_id, room_id, f"⚠️系统消息⚠️\n该模式暂不可用({enableGPT4})", is_room)

    elif (not is_room or (is_room and is_mention)) and content.startswith(
        resetChatKey
    ):  # todo
        if is_room:
            chatbots.pop((wx_id, room_id), None)
        else:
            chatbots.pop((wx_id, ""), None)
        __reply(wx_id, room_id, "⚠️系统消息⚠️\n重置对话与设置...", is_room)

    elif (not is_room or (is_room and is_mention)) and content.startswith(sdImgKey):
        __reply(wx_id, room_id, "⚠️系统消息⚠️\n 正在为您生成图片...", is_room)
        content = re.sub("^" + sdImgKey, "", content, 1).lstrip()

        try:
            content = translate(content)

        except Exception as error:
            print("!!", error)
            reply = "⚠️系统信息⚠️\n\n服务不可用，请稍后尝试..."

        print(f"-- prompt: {content}")

        prompt_list = re.split(sdNegativePromptKey, content)

        ig = ImgTask(ws, prompt_list, wx_id, room_id, is_room, "2.1")
        img_que.put(ig)

    elif (not is_room or (is_room and is_mention)) and content.startswith(midImgKey):
        # __reply(wx_id, room_id, "⚠️系统消息⚠️\n 正在为您生成图片 （Mid v5）...", is_room)

        # content = re.sub("^" + midImgKey, "", content, 1).lstrip()

        # prompt_parts = re.split(midParamKey, content)

        # try:
        #     prompt = f"{translate(prompt_parts[0])}{prompt_parts[1] if midParamKey in content else ''}"

        # except Exception as error:
        #     print("!!", error)
        #     reply = "⚠️系统信息⚠️\n\n翻译服务不可用，请稍后尝试..."
        #     return

        # print(f"-- prompt: {prompt}")

        # task = MJImgTask(ws, prompt, wx_id, room_id, is_room, room_replies)
        # img_que.put(task)
        __reply(wx_id, room_id, f"⚠️系统消息⚠️\n该模式暂不可用({midImgKey})", is_room)

    elif (
        autoReply
        and is_ask
        and (
            (not is_room and privateReplyMode)
            # check if it's mention
            or (is_room and groupReplyMode and is_mention)
        )
    ):
        if chatbot is None:
            chatbot = ChatGPTbot(
                api_key=local_config["api_key"], proxy=local_config["proxy"]
            )
            # chatbot = ChatGPTbotUnofficial(
            #     rev_config,
            #     conversation_id=None,
            #     parent_id=None,
            # )
            if is_room:
                chatbots[(wx_id, room_id)] = chatbot
            else:
                chatbots[(wx_id, "")] = chatbot

            # chatbot = BingBot(cookiePath="./.config/bing_cookies.json")
            # if is_room:
            #     chatbots[(wx_id, room_id)] = chatbot
            # else:
            #     chatbots[(wx_id, "")] = chatbot

        task = ChatTask(chatbot, ws, content, wx_id, room_id, is_room, room_replies)
        chat_que.put(task)

    elif content.startswith(regenerateKey):  # todo
        pass

    elif content.startswith(rollbackKey):  # todo
        pass

    else:
        return


def __reply(wx_id, room_id, reply, is_room=False):
    if is_room:
        # ws.send(send_txt_msg(text_string=reply, wx_id=room_id))

        # queue replies
        if not (wx_id, room_id) in room_replies:
            room_replies[(wx_id, room_id)] = [reply]
        else:
            room_replies[(wx_id, room_id)].append(reply)

        ws.send(get_chat_nick_p(wx_id=wx_id, room_id=room_id))
        # ws.send(send_at_meg(wx_id=wx_id, room_id=room_id, content=reply, nickname=wx_id))

    else:
        ws.send(send_txt_msg(text_string=reply, wx_id=wx_id))


def handle_recv_pic_msg(j):
    print(j)


def handle_recv_txt_cite(j):
    print(j)
    data = j["content"]
    root = ET.fromstring(data["content"])

    title = root[0][0].text

    msg = {"id1": data["id2"], "wxid": data["id1"], "content": title}

    handle_recv_txt_msg(msg)


def handle_heartbeat(j):
    print(j)


def handle_personal_info(j):
    print(j)
    content = json.loads(j["content"])
    global_context["wx_name"] = content["wx_name"]


def on_open(ws):
    # chatbot = ChatGPTbotUnofficial(
    #     rev_config,
    #     conversation_id=None,
    #     parent_id=None,
    # )
    # try:
    #     chatbot.login()
    # except Exception:
    #     raise Exception("Exception detected, check revChatGPT login config")
    # else:
    #     print("\nChatGPT login test success!\n")

    # ws.send(send_wxuser_list())  # 获取微信通讯录好友列表
    # ws.send(get_chatroom_memberlist())
    ws.send(get_personal_info())

    # ws.send(send_txt_msg("server is online", "filehelper"))

    # ws.send(send_txt_msg())     # 向你的好友发送微信文本消息

    for i in range(0, 2):
        chat_processor = Processor(chat_que)
        global_thread.append(chat_processor)

    for i in range(0, 4):
        image_processor = Processor(img_que)
        global_thread.append(image_processor)


def on_message(ws, message):
    j = json.loads(message)
    # print(j)

    resp_type = j["type"]

    # switch
    action = {
        HEART_BEAT: handle_heartbeat,
        RECV_TXT_MSG: handle_recv_txt_msg,
        RECV_PIC_MSG: handle_recv_pic_msg,
        NEW_FRIEND_REQUEST: print,
        RECV_TXT_CITE_MSG: handle_recv_txt_cite,
        TXT_MSG: print,
        PIC_MSG: print,
        AT_MSG: print,
        USER_LIST: handle_wxuser_list,
        GET_USER_LIST_SUCCSESS: handle_wxuser_list,
        GET_USER_LIST_FAIL: handle_wxuser_list,
        ATTACH_FILE: print,
        CHATROOM_MEMBER: hanle_memberlist,
        CHATROOM_MEMBER_NICK: handle_nick,
        DEBUG_SWITCH: print,
        PERSONAL_INFO: handle_personal_info,
        PERSONAL_DETAIL: print,
    }

    action.get(resp_type, print)(j)


def on_error(ws, error):
    print(ws)
    print(error)


def on_close(ws):
    for key, value in chatbots:  # todo: still have bugs
        print("clear conversation id:" + value.parent_id)
        value.clear_conversations()

    print(ws)
    print("closed")


server = "ws://" + server_host

websocket.enableTrace(True)

ws = websocket.WebSocketApp(
    server, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close
)
