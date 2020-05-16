import json
import logging
import random
import IPython
import asyncio

from aiortc import RTCIceCandidate, RTCSessionDescription
from aiortc.contrib.signaling import object_from_string, object_to_string, BYE
from aiortc.contrib.signaling import ApprtcSignaling

from server import FilesystemRTCServer

try:
    import aiohttp
    import websockets
except ImportError:  # pragma: no cover
    aiohttp = None
    websockets = None

logger = logging.getLogger("colabrtc.signaling")

try:
    from google.colab import output
except ImportError:
    output = None
    logger.info('google.colab not available')
    

class ColabApprtcSignaling(ApprtcSignaling):
    def __init__(self, room=None, javacript_callable=False):
        super().__init__(room)

        self._javascript_callable = javacript_callable

        if output and javacript_callable:
            output.register_callback(f'{room}.colab.signaling.connect', self.connect_sync)
            output.register_callback(f'{room}.colab.signaling.send', self.send_sync)
            output.register_callback(f'{room}.colab.signaling.receive', self.receive_sync)
            output.register_callback(f'{room}.colab.signaling.close', self.close_sync)
            
    @property
    def room(self):
        return self._room

    async def connect(self):
        join_url = self._origin + "/join/" + self._room

        # fetch room parameters
        self._http = aiohttp.ClientSession()
        async with self._http.post(join_url) as response:
            # we cannot use response.json() due to:
            # https://github.com/webrtc/apprtc/issues/562
            data = json.loads(await response.text())
        assert data["result"] == "SUCCESS"
        params = data["params"]

        self.__is_initiator = params["is_initiator"] == "true"
        self.__messages = params["messages"]
        self.__post_url = (
            self._origin + "/message/" + self._room + "/" + params["client_id"]
        )

        # connect to websocket
        self._websocket = await websockets.connect(
            params["wss_url"], extra_headers={"Origin": self._origin}
        )
        await self._websocket.send(
            json.dumps(
                {
                    "clientid": params["client_id"],
                    "cmd": "register",
                    "roomid": params["room_id"],
                }
            )
        )

        print(f"AppRTC room is {params['room_id']} {params['room_link']}")

        return params
            
    def connect_sync(self):
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.connect())
        if self._javascript_callable:
            return IPython.display.JSON(result)
        return result
            
    def close_sync(self):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.close())
    
    def recv_nowait(self):
        try:
            return self._websocket.messages.popleft() # .get_nowait()
        #except (asyncio.queues.QueueEmpty, IndexError):
        except IndexError:
            pass
        
    async def receive(self):
        if self.__messages:
            message = self.__messages.pop(0)
        else:
            message = self.recv_nowait()
            if message:
                message = json.loads(message)["msg"]
        
        if message:
            logger.debug("< " + message)
            return object_from_string(message)
    
    def receive_sync(self):
        loop = asyncio.get_event_loop()
        message = loop.run_until_complete(self.receive())
        if message and self._javascript_callable:
            message = object_to_string(message)
            print('receive:', message)
            message = json.loads(message)
            message = IPython.display.JSON(message)
        return message
    
    async def send(self, obj):
        message = object_to_string(obj)
        logger.debug("> " + message)
        if self.__is_initiator:
            await self._http.post(self.__post_url, data=message)
        else:
            await self._websocket.send(json.dumps({"cmd": "send", "msg": message}))
        
    def send_sync(self, message):
        print('send:', message)
        if type(message) == str:
            message_json = json.loads(message)
            if 'candidate' in message_json:
                message_json['type'] = 'candidate'
                message_json["id"] = message_json["sdpMid"]
                message_json["label"] = message_json["sdpMLineIndex"]
                message = json.dumps(message_json)  
                message = object_from_string(message)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.send(message))
    

class ColabSignaling:
    def __init__(self, signaling_folder=None, webrtc_server=None, room=None, javacript_callable=False):
        if room is None:
            room = "".join([random.choice("0123456789") for x in range(10)])

        if webrtc_server is None and signaling_folder is None:
            raise ValueError('Either a WebRTC server or a signaling folder must be provided.')
        if webrtc_server is None:
            self._webrtc_server = FilesystemRTCServer(folder=signaling_folder)
        else:
            self._webrtc_server = webrtc_server
            
        self._room = room
        self._javascript_callable = javacript_callable

        if output and javacript_callable:
            output.register_callback(f'{room}.colab.signaling.connect', self.connect_sync)
            output.register_callback(f'{room}.colab.signaling.send', self.send_sync)
            output.register_callback(f'{room}.colab.signaling.receive', self.receive_sync)
            output.register_callback(f'{room}.colab.signaling.close', self.close_sync)

    @property
    def room(self):
        return self._room
            
    async def connect(self):
        data = self._webrtc_server.join(self._room)
        assert data["result"] == "SUCCESS"
        params = data["params"]

        self.__is_initiator = params["is_initiator"] == "true"
        self.__messages = params["messages"]
        self.__peer_id = params["peer_id"]
        
        logger.info(f"Room ID: {params['room_id']}")
        logger.info(f"Peer ID: {self.__peer_id}")
        return params

    def connect_sync(self):
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.connect())
        if self._javascript_callable:
            return IPython.display.JSON(result)
        return result
            
    async def close(self):
        if self._javascript_callable:
            return self.send_sync(BYE)
        else:
            await self.send(BYE)

    def close_sync(self):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.close())
    
    async def receive(self):
        message = self._webrtc_server.receive_message(self._room, self.__peer_id)
        # if self._javascript_callable:
        #     print('ColabSignaling: sending message to Javascript peer:', message)
        # else:
        #     print('ColabSignaling: sending message to Python peer:', message)
        if message and type(message) == str and not self._javascript_callable:
            message = object_from_string(message)
        return message

    def receive_sync(self):
        loop = asyncio.get_event_loop()
        message = loop.run_until_complete(self.receive())
        if message and self._javascript_callable:
            message = json.loads(message)
            message = IPython.display.JSON(message)
        return message
        
    async def send(self, message):
        if not self._javascript_callable or type(message) != str:
            message = object_to_string(message)
        self._webrtc_server.send_message(self._room, self.__peer_id, message)
        
    def send_sync(self, message):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.send(message))
