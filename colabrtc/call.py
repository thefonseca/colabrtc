import os

import nest_asyncio
from IPython.display import display, Javascript
from google.colab.output import eval_js

from signaling import ColabSignaling, ColabApprtcSignaling
from peer import start_peer

nest_asyncio.apply()


class ColabCall:
    def __init__(self, signaling_js='js/signaling.js', peer_js='js/peer.js',
                 peer_ui_js='js/peer-ui.js'):
        
        file_path = os.path.dirname(os.path.abspath(__file__))
        js_files = [signaling_js, peer_js, peer_ui_js]
        js_content = []
        
        for js_file in js_files:
            with open(os.path.join(file_path, js_file), 'r') as js:
                js_content.append(js.read())

        js_content.append('''
          var start_js_peer = function(room) {    
            new PeerUI(room);
          }
          ''')
        self._js = ' '.join(js_content)
        self._peer_process = None
        self.room = None
        self.signaling_folder = None

    def create(self, room=None, signaling_folder='/content/webrtc',
               frame_transformer=None, verbose=False, multiprocess=True):

        self.end()

        room, proc = start_peer(room, signaling_folder=signaling_folder,
                                frame_transformer=frame_transformer,
                                verbose=verbose, multiprocess=multiprocess)
        self._peer_process = proc
        self.room = room
        self.signaling_folder = signaling_folder
        self.js_signaling = None

    def join(self, room=None, signaling_folder='/content/webrtc', verbose=False):
        if self.room is None and room is None:
            raise ValueError('A room parameter must be specified')
        elif self.room:
            room = self.room

        if self.signaling_folder and self.signaling_folder != signaling_folder:
            signaling_folder = self.signaling_folder

        if signaling_folder:
            self.js_signaling = ColabSignaling(signaling_folder=signaling_folder, 
                                               room=room, javacript_callable=True)
        else:
            self.js_signaling = ColabApprtcSignaling(room=room, javacript_callable=True)

        display(Javascript(self._js))
        eval_js(f'start_js_peer("{room}")')
        
    def end(self):
        if self._peer_process:
            self._peer_process.terminate()
            self._peer_process.join()