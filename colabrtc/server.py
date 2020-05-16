import json
import logging
import random
import uuid
import os
import glob
import re
from datetime import datetime



logger = logging.getLogger("colabrtc.server")


class Room():
    _folder_prefix = 'room'

    def __init__(self, room_id, parent_folder='webrtc'):
        if not Room.is_valid_id(room_id):
            raise ValueError(f'Room ID must have only numbers, letters, "_", "@", and ".": {room_id}')

        self._room_id = room_id
        self._parent_folder = parent_folder
        self._folder = os.path.join(self._parent_folder, 
                                    f'{Room._folder_prefix}_{self._room_id}')
        self._messages = []
        self._peers = {}

    @staticmethod
    def is_valid_id(room_id):
        return re.match(r'^[a-zA-Z0-9_@\.]+$', room_id)

    @staticmethod
    def is_valid_folder(folder):
        return re.match(f'{Room._folder_prefix}_\d{10}', folder)

    @staticmethod
    def get_id_from_folder(folder):
        folder = os.path.basename(os.path.normpath(folder))
        if Room.is_valid_folder(folder):
            room_id = folder.replace(f'{Room._folder_prefix}_', '')
            return room_id

    @property
    def room_id(self):
        return self._room_id

    @property
    def folder(self):
        return self._folder

    @property
    def messages(self):
        return self._messages

    @property
    def peers(self):
        return self._peers

    def add_peer(self, peer):
        if peer:
            self._peers[peer.peer_id] = peer
        
    def add_message(self, message):
        self._messages.append(message)

    def get_peer(self, peer_id):
        return self._peers.get(peer_id)

    def save(self):
        for message in self._messages:
            message.save()    

        for p_id, peer in self._peers.items():
            peer.room = self
            peer.save()

    def load(self, create=False):
        if create:
            os.makedirs(self._folder, exist_ok=True)
        elif not os.path.exists:
            raise ValueError(f'Room with id {self._room_id} does not exist')

        self._peers = Peer.load_peers(self)
        self._messages = Message.load_messages(self._folder)
        for msg in self._messages:
            msg.room = self
        return self


class Peer():
    _folder_prefix = 'peer'

    def __init__(self, room, peer_id=None):
        if not peer_id:
            peer_id = "".join([random.choice("0123456789") for x in range(10)])

        self._peer_id = peer_id
        self.room = room
        self._folder = f'{Peer._folder_prefix}_{peer_id}'
        self._folder = os.path.join(room.folder, self._folder)
        os.makedirs(self._folder, exist_ok=True)
        self._messages = []
        self._is_initiator = False
        # self._registered = False
        room.add_peer(self)
        
    @staticmethod
    def is_valid_folder(folder):
        return re.match(f'{Peer._folder_prefix}_.+', folder)

    @staticmethod
    def get_id_from_folder(folder):
        folder = os.path.basename(os.path.normpath(folder))
        if Peer.is_valid_folder(folder):
            peer_id = folder.replace(f'{Peer._folder_prefix}_', '')
            return peer_id

    @staticmethod
    def load_peers(room):
        peers = {}
        file_pattern = os.path.join(room.folder, f'{Peer._folder_prefix}_*')
        for peer_folder in glob.glob(file_pattern):
            peer_id = Peer.get_id_from_folder(peer_folder)
            if peer_id:
                peer = Peer(room, peer_id).load()
                if peer:
                    peers[peer_id] = peer
        return peers

    @property
    def peer_id(self):
        return self._peer_id

    @property
    def is_initiator(self):
        return self._is_initiator

    @property
    def folder(self):
        return self._folder

    @property
    def messages(self):
        return self._messages

    @is_initiator.setter 
    def is_initiator(self, value):
        self._is_initiator = value

    def to_json(self):
        return {
            'id': self._peer_id,
            'room_id': self.room.room_id,
            'is_initiator': self._is_initiator
            #'registered': self._registered
        }

    def add_message(self, message):
        self._messages.append(message)

    def save(self):
        peer_data_file = os.path.join(self._folder, 'peer.json')
        if not os.path.exists(peer_data_file):
            with open(peer_data_file, 'w') as json_file:
                json.dump(self.to_json(), json_file)

        for message in self._messages:
            message.save()

    def load(self):
        peer_data_file = os.path.join(self._folder, 'peer.json')
        if not os.path.exists(peer_data_file):
            return
        
        with open(peer_data_file, 'r') as json_file:
            peer_data = json.load(json_file)
            self._is_initiator = peer_data['is_initiator']
            # self._registered = peer_data['registered']

        self._messages = Message.load_messages(self._folder)
        for msg in self._messages:
            msg.peer = self
            msg.room = self.room
        return self


class Message():
    _prefix = 'msg'
    _read_prefix = 'read'
    _extension = 'txt'

    def __init__(self, sender_id, message_id=None, msg_type=None, 
                 content=None, room=None, peer=None):
        if not message_id:
            now = datetime.now()
            message_id = str(datetime.timestamp(now))
        self._message_id = message_id
        self._sender_id = sender_id
        self.room = room
        self.peer = peer
        self._msg_type = msg_type
        self.content = content
        self._is_read = False

        if room:
            room.add_message(self)
        if peer:
            peer.add_message(self)
        
    @staticmethod
    def is_valid_filename(filename):
        pattern = f'({Message._read_prefix}_)?{Message._prefix}_.+\.{Message._extension}'
        return re.match(pattern, filename)

    @staticmethod
    def get_id_from_folder(folder):
        filename = os.path.basename(os.path.normpath(folder))
        if Message.is_valid_filename(filename):
            message_id = filename.replace(f'{Message._prefix}_', '')
            message_id = message_id.replace(f'{Message._read_prefix}_', '')
            message_id = message_id.replace(f'.{Message._extension}', '')
            message_split = message_id.split('_')
            message_type = None
            sender_id = None

            if len(message_split) > 1:
                sender_id = message_split[2]
                message_type = message_split[1]
                message_id = message_split[0]
            
            return message_id, message_type, sender_id

    @staticmethod
    def load_messages(folder):
        messages = []
        file_pattern = os.path.join(folder, f'{Message._prefix}_*')
        for message_folder in glob.glob(file_pattern):
            msg_id, msg_type, sender_id = Message.get_id_from_folder(message_folder)
            if msg_id:
                message = Message(sender_id, message_id=msg_id, 
                                  msg_type=msg_type).load(message_folder)
                messages.append(message)
        return messages

    @property
    def message_id(self):
        return self._message_id

    @property
    def msg_type(self):
        return self._msg_type

    @msg_type.setter
    def msg_type(self, value):
        self._msg_type = value

    @property
    def is_read(self):
        return self._is_read

    @is_read.setter
    def is_read(self, value):
        self._is_read = value

    def _get_filename(self):
        # message["id"] is the message timestamp
        msg_filename = f'{Message._prefix}_{self._message_id}'

        if self._msg_type:
            msg_filename = f'{msg_filename}_{self._msg_type}'
        
        if self._is_read:
            """
            Add read prefix, so messages are not received multiple times.
            TODO: use timestamps for more robust message receipt verification.
            E.g.: the peer could call receive sending as parameter the timestamp
            of the last message succesfully read, and the server would return 
            the next message given the informed timestamp. Prefixes would be 
            still useful for inspecting message exchange using the file browser.
            """
            msg_filename = f'{Message._read_prefix}_{msg_filename}'
            
        msg_filename = f'{msg_filename}_{self._sender_id}'
        msg_filename = f'{msg_filename}.{Message._extension}'
        return msg_filename

    def _save_to_folder(self, folder):
        message_file = self._get_filename()
        message_file = os.path.join(folder, message_file)
        
        if self._is_read:
            unread_file = message_file.replace(f'{Message._read_prefix}_', '')
            unread_file = os.path.join(folder, unread_file)

            if os.path.exists(unread_file):
                os.rename(unread_file, message_file)

        if not os.path.exists(message_file):
            with open(message_file, 'w') as txt_file:
                txt_file.write(self.content)
    
    def save(self):
        if self.room:
            self._save_to_folder(self.room.folder)
        if self.peer:
            self._save_to_folder(self.peer.folder)

    def load(self, folder=None):
        message_filename = self._get_filename()

        if folder:
            message_file = folder
        elif self.room:
            message_file = os.path.join(self.room.folder, message_filename)
        elif self.peer:
            message_file = os.path.join(self.peer.folder, message_filename)

        with open(message_file, 'r') as txt_file:
            self.content = txt_file.read()
        return self


class FilesystemRTCServer:
    def __init__(self, folder='webrtc'):
        self._folder = folder
        os.makedirs(folder, exist_ok=True)

    def _get_room(self, room_id, create=False):
        return Room(room_id, parent_folder=self._folder).load(create=create)

    def _get_peer(self, room_id, peer_id):
        room = self._get_room(room_id)
        peer = room.get_peer(peer_id)
        if not peer:
            raise ValueError(f'invalid peer id: {peer_id}')
        return peer
        
    def join(self, room_id):
        room = self._get_room(room_id, create=True)
        new_peer = Peer(room)
        
        relevant_messages = [msg for msg in room.messages if msg.msg_type in ['offer', 'candidate']]
        if len(relevant_messages) == 0 or len(room.peers) == 0:
            new_peer.is_initiator = True
            
        room.save()
        
        if relevant_messages:
            logger.debug(f'> {len(room.messages)} messages in room {room_id}')
        for message in relevant_messages:
            message.peer = new_peer
            message.save()
        
        params = {
            'messages': None,
            'room_id': room_id,
            'peer_id': new_peer.peer_id,
            'is_initiator': new_peer.is_initiator
        }
        
        response = {'result': 'SUCCESS'}
        response['params'] = params
        return response

    def receive_message(self, room_id, peer_id):
        try:
            peer = self._get_peer(room_id, peer_id)
            messages = peer.messages
            if messages:
                message = messages[0]
                message.is_read = True
                message.save()
                return message.content
        except ValueError as err:
            return {'result': 'error', 'reason': str(err)}

    def send_message(self, room_id, peer_id, message_str):
        try:
            room = self._get_room(room_id)
            peer = room.get_peer(peer_id)
            message = Message(sender_id=peer.peer_id, room=room, 
                              content=message_str)
            
            message_json = json.loads(message_str)
            if 'type' in message_json:
                message.msg_type = message_json['type']
            elif 'candidate' in message_json:
                message.msg_type = 'candidate'
                message_json['type'] = 'candidate'
                message_json["id"] = message_json["sdpMid"]
                message_json["label"] = message_json["sdpMLineIndex"]
                message.content = json.dumps(message_json)
                message.candidate = message_json['candidate']
            else:
                message.msg_type = 'other'
                message_json['type'] = 'other'
                message.content = json.dumps(message_json)

            message.save()
            for p_id, peer in room.peers.items():
                if peer.peer_id == peer_id:
                    continue
                message.peer = peer
                message.save()

        except ValueError as err:
            return {'result': 'error', 'reason': str(err)}
