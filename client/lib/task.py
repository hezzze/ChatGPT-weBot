import asyncio
import json
import time
import threading

from shared import *
from revChat.V1 import Chatbot as ChatGPTbotUnofficial
from bing.EdgeGPT import Chatbot as BingBot
from revChat.V3 import Chatbot as ChatGPTbot

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


class ChatTask:
    def __init__(self, chatbot, ws, content, wx_id, room_id, is_room, room_replies):
        self.ws = ws
        self.content = content
        self.bot = chatbot
        self.wx_id = wx_id
        self.room_id = room_id
        self.is_room = is_room
        self.room_replies = room_replies
        self.lock = threading.Lock()

    def play(self):
        print("ask:" + self.content)
        reply = ""

        try:
            if isinstance(self.chatbot, ChatGPTbotUnofficial):
                for data in self.chatbot.ask(
                    prompt=self.content,
                ):
                    reply += data["message"][len(reply) :]
            elif isinstance(self.chatbot, BingBot):
                reply = loop.run_until_complete(self.chatbot.ask(prompt=self.content))[
                    "item"
                ]["messages"][1]["adaptiveCards"][0]["body"][0]["text"]
            elif isinstance(self.chatbot, ChatGPTbot):
                reply += self.chatbot.ask(self.content)

        except Exception as error:
            print("!!!", error)
            reply = "<系统信息>\n服务暂时不可用，请稍后尝试..."

        # reply = f"###testing, replying to {wx_id}..."

        self.__reply(reply)

        print("reply:" + reply)

    def __reply(self, reply):
        if self.is_room:
            # ws.send(send_txt_msg(text_string=reply, wx_id=room_id))

            # queue replies

            with self.lock:  # need thread safety
                if not (self.wx_id, self.room_id) in self.room_replies:
                    self.room_replies[(self.wx_id, self.room_id)] = [reply]
                else:
                    self.room_replies[(self.wx_id, self.room_id)].append(reply)

            self.ws.send(get_chat_nick_p(wx_id=self.wx_id, room_id=self.room_id))
            # ws.send(send_at_meg(wx_id=wx_id, room_id=room_id, content=reply, nickname=wx_id))

        else:
            self.ws.send(send_txt_msg(text_string=reply, wx_id=self.wx_id))
