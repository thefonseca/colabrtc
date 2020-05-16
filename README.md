ColabRTC
==========

`ColabRTC` contains early experiments to stream media 
from your machine to a Google Colab instance using 
`Web Real-Time Communication (WebRTC)`. It is built on top of
[aiortc](https://github.com/aiortc/aiortc).

The motivation behind this project was to to learn about WebRTC
 and because an efficient implementation of this kind of communication
 could be useful to prototype Deep Learning models without a local
 GPU. 

 How to use ``colabrtc``?
------------------------

The API allows one to create a `ColabCall`, which consists of a
Python peer (running on Colab) and a Javascript peer 
(started in a Colab cell HTML context, which runs on the 
local machine). The signaling medium is the Colab filesystem 
(and Google Drive, optionally).

An example:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/thefonseca/colabrtc/blob/master/examples/colabrtc.ipynb)

```
from call import ColabCall
import cv2

# Define a frame processing routine
def process_frame(frame, frame_idx):
  # To speed up, apply processing every two frames
  if frame_idx % 2 == 1:
    edges = cv2.Canny(frame, 100, 200)
    return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
  
call = ColabCall()
# Create the Python peer
call.create(frame_transformer=process_frame)
# Create the Javascript peer and display the UI
call.join()
```







