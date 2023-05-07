import asyncio
import json
import time
import threading
import string
import random
import base64
import os.path
import websocket
from websockets import connect

from client.lib.shared import *
from revChatGPT.V1 import Chatbot as ChatGPTbotUnofficial
from bing.EdgeGPT import Chatbot as BingBot
from revChatGPT.V3 import Chatbot as ChatGPTbot

loop = asyncio.get_event_loop()

from client.lib.local_config import local_config


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


def send_pic_msg(wx_id, content):
    qs = {
        "id": getid(),
        "type": PIC_MSG,
        "wxid": wx_id,
        "roomid": "",
        "content": content,
        "nickname": "",
        "ext": "",
    }
    s = json.dumps(qs)
    return s


class ChatTask:
    def __init__(self, chatbot, ws, content, wx_id, room_id, is_room, room_replies):
        self.chatbot = chatbot
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
            reply = "⚠️系统消息⚠️\n服务暂时不可用，请稍后尝试..."

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


class ImgTask:
    def __init__(self, ws, prompt, wx_id, room_id, is_room, version):
        self.ws = ws
        self.prompt = prompt
        self.wx_id = wx_id
        self.room_id = room_id
        self.is_room = is_room
        self.version = version

        self.img_ws = None
        self.wssRq = {
            "session_hash": "".join(
                random.sample(string.ascii_lowercase + string.digits, 11)
            ),
            "fn_index": 3,
        }
        self.times = 0

        if version == "2.1":
            self.img_host = "wss://" + API_URL_v21
        elif version == "1.5":
            self.img_host = "wss://" + API_URL_v15

    def on_open(self, img_ws):
        self.times += 1
        img_ws.send(json.dumps(self.wssRq))

    def on_message(self, img_ws, message):
        msg = json.loads(message)

        if msg["msg"] == "queue_full":
            if self.times < 5:
                # raise
                send_txt_msg(
                    text_string="⚠️系统消息⚠️\n\n连接Stable diffuison 发生错误，请稍后尝试...",
                    wx_id=self.room_id if self.is_room else self.wx_id,
                )
            else:
                self.times += 1
                img_ws.send(json.dumps(self.wssRq))

        elif msg["msg"] == "send_data":
            process = {
                "data": [
                    self.prompt[0],
                    "" if len(self.prompt) == 1 else self.prompt[1],
                    9,
                ],
                "fn_index": 3,
            }
            img_ws.send(json.dumps(process))

        elif msg["msg"] == "process_starts":
            print(message)

        elif msg["msg"] == "process_completed":
            for item in msg["output"]["data"][0]:
                source_str = base64.urlsafe_b64decode(item[23:])
                filename = self.wx_id + "_" + self.room_id + "_" + getid() + ".jpg"
                if not os.path.exists(".cache/"):
                    os.makedirs(cache_dir)
                with open(cache_dir + filename, "wb") as file_object:
                    file_object.write(source_str)
                file_object.close()

                self.ws.send(
                    send_pic_msg(
                        wx_id=self.room_id if self.is_room else self.wx_id,
                        content=os.path.join(os.path.abspath(cache_dir), filename),
                    )
                )
                time.sleep(1.0)
                # if isCached:
                #     print("Image cached! Name: " + cache_dir + filename)
                # else:
                #     os.remove(cache_dir + filename)
                os.remove(cache_dir + filename)

    def on_error(self, img_ws, error):
        print(error)

    def on_close(self, img_ws):
        print("Stable Diffusion V" + self.version + " arts are done!")

    def play(self):
        self.img_ws = websocket.WebSocketApp(
            self.img_host,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        self.img_ws.keep_running = False
        self.img_ws.run_forever()


class MJImgTask:
    def __init__(self, ws, prompt, wx_id, room_id, is_room, room_replies):
        self.ws = ws
        self.prompt = prompt
        self.wx_id = wx_id
        self.room_id = room_id
        self.is_room = is_room

        self.img_ws = None
        self.lock = threading.Lock()
        self.room_replies = room_replies

    def play(self):
        try:
            asyncio.run(self.request())

        except Exception as error:
            print("!!", error)
            reply = "⚠️系统消息⚠️\n\n未知错误，请稍后尝试..."
            self.__reply(reply)


    async def wait_for_image(self, websocket):
         while True:
            # if the websocket is closed prematurely 
            # the following will raise an exception which is intended
            # timeout set as ping_timeout 
            decoded = json.loads(await websocket.recv())
            
            print(decoded)
            if decoded["message"] == "completed":
                for file_name in decoded["files"]:
                    self.ws.send(
                        send_pic_msg(
                            wx_id=self.room_id if self.is_room else self.wx_id,
                            content=os.path.join(
                                local_config["image_folder"], file_name
                            ),
                        )
                    )
                    time.sleep(1.0)

                break



    async def request(self):
        async with connect(uri=local_config["socket_uri"], ping_timeout=120) as websocket:
            await websocket.send(
                json.dumps(
                    [
                        "generate_image",
                        {
                            "prompt": self.prompt,
                        },
                    ]
                )
            )

            try:
                await asyncio.wait_for(self.wait_for_image(websocket), timeout=240)
    
            except asyncio.TimeoutError:
                reply = "⚠️系统消息⚠️\n 生成图片超时，请稍后再试..."
                self.__reply(reply)
                await websocket.close()
    

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
