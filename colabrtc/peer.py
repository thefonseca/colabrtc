import argparse
import asyncio
import logging
import os
import random
from abc import ABC, abstractmethod
from multiprocessing import Process

# try:
#     from torch.multiprocessing import Process, set_start_method
#     set_start_method('forkserver')
# except (ImportError, RuntimeError):
#     from multiprocessing import Process

import fire
import cv2
from av import VideoFrame

from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
    RTCConfiguration, RTCIceServer
)
from aiortc.mediastreams import MediaStreamError
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder, MediaRecorderContext
from aiortc.contrib.signaling import BYE
from server import FilesystemRTCServer
from signaling import ColabSignaling, ColabApprtcSignaling

import pathlib
THIS_FOLDER = pathlib.Path(__file__).parent.absolute()
PHOTO_PATH = os.path.join(THIS_FOLDER, 'photo.jpg')

#logging.basicConfig(filename='peer.txt', filemode='w', format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("colabrtc.peer")


class VideoImageTrack(VideoStreamTrack):
    """
    A video stream track that returns a rotating image.
    """

    def __init__(self):
        super().__init__()  # don't forget this!
        self.img = cv2.imread(PHOTO_PATH, cv2.IMREAD_COLOR)

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        
        # rotate image
        rows, cols, _ = self.img.shape
        M = cv2.getRotationMatrix2D((cols / 2, rows / 2), int(pts * time_base * 45), 1)
        img = cv2.warpAffine(self.img, M, (cols, rows))

        # create video frame
        frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base

        return frame


class FrameTransformer(ABC):
    @abstractmethod
    def setup(self):
        ...
    @abstractmethod
    def transform(self, frame, frame_idx):
        ...


class VideoTransformTrack(VideoStreamTrack):
    """
    A video stream track that returns a rotating image.
    """

    def __init__(self, track, frame_transformer):
        super().__init__()  # don't forget this!
        
        if frame_transformer is None:
            frame_transformer = lambda x, y: x
        elif isinstance(frame_transformer, FrameTransformer):
            # frame_transformer = frame_transformer()
            frame_transformer.setup()
        self.__frame_transformer = frame_transformer
        
        self.track = track
        self.frame_idx = 0
        self.last_img = None
        
    async def recv(self):
        if self.track:
            frame = await self.track.recv()
            img = None
            
            try:
                # process video frame
                frame_img = frame.to_ndarray(format='bgr24')
                if isinstance(self.__frame_transformer, FrameTransformer):
                    img = self.__frame_transformer.transform(frame_img, self.frame_idx)
                else:
                    img = self.__frame_transformer(frame_img, self.frame_idx)
            except Exception as ex:
                logger.error(ex)
            
            if img is None and self.last_img is None:
                img = frame.to_ndarray(format='bgr24')
            elif img is None:
                img = self.last_img
            else:
                self.last_img = img
            
            self.frame_idx += 1
        else:
            img = np.zeros((640, 480, 3))
            
        # rebuild a VideoFrame, preserving timing information
        new_frame = VideoFrame.from_ndarray(img, format='bgr24')
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base
        return new_frame
    

async def run(pc, player, recorder, signaling, frame_transformer=None):
    
    video_transform = VideoTransformTrack(None, frame_transformer)
    
    def add_tracks():
        if player and player.audio:
            pc.addTrack(player.audio)

        if player and player.video:
            pc.addTrack(player.video)
        else:
            pc.addTrack(video_transform)
            # pc.addTrack(VideoImageTrack())

    @pc.on("track")
    def on_track(track):
        logger.debug("Track %s received" % track.kind)
        #recorder.addTrack(track)
        
        if track.kind == 'video':
            #pc.addTrack(local_video)
            video_transform.track = track

    # connect to websocket and join
    params = await signaling.connect()
    if params["is_initiator"] == True:
        # send offer
        logger.debug('Sending OFFER...')
        add_tracks()
        await pc.setLocalDescription(await pc.createOffer())
        await signaling.send(pc.localDescription)
        
    # consume signaling
    while True:
        # print('>> Python: Waiting for SDP message...')
        obj = await signaling.receive()
        if obj is None:
            await asyncio.sleep(1)
            continue

        if isinstance(obj, RTCSessionDescription):
            logger.debug(obj.type, pc.signalingState)
            if obj.type == 'answer' and pc.signalingState == 'stable':
                continue
            if obj.type == "offer" and pc.signalingState == 'have-local-offer':
                continue
                
            logger.debug(f'Received {obj.type.upper()}:', str(obj)[:100])
            await pc.setRemoteDescription(obj)
            await recorder.start()

#             if obj.type == "offer":
#                 # send answer
#                 # add_tracks()
#                 logger.info('Sending ANSWER...')
#                 await pc.setLocalDescription(await pc.createAnswer())
#                 await signaling.send(pc.localDescription)
                
        elif isinstance(obj, RTCIceCandidate):
            logger.debug('Received ICE candidate:', obj)
            pc.addIceCandidate(obj)
        elif obj is BYE:
            logger.debug('Received BYE')
            logger.debug("Exiting")
            break
            

def run_process(pc, player, recorder, signaling, frame_transformer):
    try:
        # run event loop
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            run(pc=pc, player=player, recorder=recorder, signaling=signaling, frame_transformer=frame_transformer)
        )
    except KeyboardInterrupt:
        pass
    finally:
        # cleanup
        loop.run_until_complete(recorder.stop())
        loop.run_until_complete(signaling.close())
        loop.run_until_complete(pc.close())


def start_peer(room=None, signaling_folder=None, play_from=None, record_to=None, 
               frame_transformer=None, verbose=False, ice_servers=None, multiprocess=False):
    
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if ice_servers:
        logger.debug('Using ICE servers:', ice_servers)
        servers = [RTCIceServer(*server) if type(server) == tuple else RTCIceServer(server) for server in ice_servers]
        pc = RTCPeerConnection(
            configuration=RTCConfiguration(servers))
    else:
        pc = RTCPeerConnection()
    
    # room = str(room)
    if signaling_folder:
        signaling = ColabSignaling(signaling_folder=signaling_folder, room=room)
    else:
        signaling = ColabApprtcSignaling(room=room)
        
    # create media source
    if play_from:
        player = MediaPlayer(play_from)
    else:
        player = None

    # create media sink
    if record_to:
        recorder = MediaRecorder(record_to)
    else:
        recorder = MediaBlackhole()
        
    if multiprocess:
        p = Process(target=run_process, args=(pc, player, recorder, signaling, frame_transformer))
        p.start()
        return signaling.room, p
    else:
        run_process(pc, player, recorder, signaling, frame_transformer)
        return signaling.room, None
     
    
if __name__ == '__main__':
     fire.Fire(start_peer)
