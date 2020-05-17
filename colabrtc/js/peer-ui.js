var PeerUI = function(room, container_id) {
    // Define initial start time of the call (defined as connection between peers).
    startTime = null;
    constraints = {audio: false, video: true};
    
    let peerDiv = null;
    
    if (container_id) {
        peerDiv = document.getElementById(container_id);
    } else {
        peerDiv = document.createElement('div');
        document.body.appendChild(peerDiv);
    }

    var style = document.createElement('style');
    style.type = 'text/css';
    style.innerHTML = `
        .loader {
          position: absolute;
          left: 38%;
          top: 60%;
          z-index: 1;
          width: 50px;
          height: 50px;
          margin: -75px 0 0 -75px;
          border: 16px solid #f3f3f3;
          border-radius: 50%;
          border-top: 16px solid #3498db;
          -webkit-animation: spin 2s linear infinite;
          animation: spin 2s linear infinite;
        }

        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
    `;
    document.getElementsByTagName('head')[0].appendChild(style);

    var adapter = document.createElement('script');
    adapter.setAttribute('src','https://webrtc.github.io/adapter/adapter-latest.js');
    document.getElementsByTagName('head')[0].appendChild(adapter);

    peerDiv.style.width = '70%';

    // Define video elements.
    const videoDiv = document.createElement('div');
    videoDiv.style.display = 'none';
    videoDiv.style.textAlign = '-webkit-center';
    const localView = document.createElement('video');
    const remoteView = document.createElement('video');
    remoteView.autoplay = true;
    localView.style.display = 'block';
    remoteView.style.display = 'block';
    localView.height = 240;
    localView.width = 320;
    remoteView.height = 240;
    remoteView.width = 320;
    videoDiv.appendChild(localView);
    videoDiv.appendChild(remoteView);
    const loader = document.createElement('div');
    loader.style.display = 'none';
    loader.className = 'loader';
    videoDiv.appendChild(loader);

    // Logs a message with the id and size of a video element.
    function logVideoLoaded(event) {
        const video = event.target;
        trace(`${video.id} videoWidth: ${video.videoWidth}px, ` +
            `videoHeight: ${video.videoHeight}px.`);

        localView.style.width = '20%';
        localView.style.position = 'absolute';
        remoteView.style.display = 'block';
        remoteView.style.width = '100%';
        remoteView.style.height = 'auto';
        loader.style.display = 'none';
        fullscreenButton.style.display = 'inline';
    }

    //localView.addEventListener('loadedmetadata', logVideoLoaded);
    remoteView.addEventListener('loadedmetadata', logVideoLoaded);
    //remoteView.addEventListener('onresize', logResizedVideo);

    // Define action buttons.
    const controlDiv = document.createElement('div');
    controlDiv.style.textAlign = 'center';
    const startButton = document.createElement('button');
    const fullscreenButton = document.createElement('button');
    const hangupButton = document.createElement('button');
    startButton.textContent = 'Join room: ' + room;
    fullscreenButton.textContent = 'Fullscreen';
    hangupButton.textContent = 'Hangup';
    controlDiv.appendChild(startButton);
    controlDiv.appendChild(fullscreenButton);
    controlDiv.appendChild(hangupButton);

    // Set up initial action buttons status: disable call and hangup.
    //callButton.disabled = true;
    hangupButton.style.display = 'none';
    fullscreenButton.style.display = 'none';

    peerDiv.appendChild(videoDiv);
    peerDiv.appendChild(controlDiv);

    this.localView = localView;
    this.remoteView = remoteView;
    this.peerDiv = peerDiv;
    this.videoDiv = videoDiv;
    this.loader = loader;
    this.startButton = startButton;
    this.fullscreenButton = fullscreenButton;
    this.hangupButton = hangupButton;
    this.constraints = constraints;
    this.room = room;

    self = this;
    async function start() {
        await self.connect(this.room);
    }

    // Handles hangup action: ends up call, closes connections and resets peers.
    async function hangup() {
        await self.disconnect();
    }

    function openFullscreen() {
      let elem = remoteView;
      if (elem.requestFullscreen) {
        elem.requestFullscreen();
      } else if (elem.mozRequestFullScreen) { /* Firefox */
        elem.mozRequestFullScreen();
      } else if (elem.webkitRequestFullscreen) { /* Chrome, Safari & Opera */
        elem.webkitRequestFullscreen();
      } else if (elem.msRequestFullscreen) { /* IE/Edge */
        elem.msRequestFullscreen();
      }
    }

    // Add click event handlers for buttons.
    this.startButton.addEventListener('click', start);
    this.fullscreenButton.addEventListener('click', openFullscreen);
    this.hangupButton.addEventListener('click', hangup);
};


PeerUI.prototype.connect = async function(room) {
    //startButton.disabled = true;
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    this.localView.srcObject = stream;
    this.localView.play();
    trace('Received local stream.');

    this.loader.style.display = 'block';
    this.startButton.style.display = 'none';
    this.localView.style.width = '100%';
    this.localView.style.height = 'auto';
    this.localView.style.position = 'relative';
    this.remoteView.style.display = 'none';
    this.videoDiv.style.display = 'block';

    if (google) {
      // Resize the output to fit the video element.
      google.colab.output.setIframeHeight(document.documentElement.scrollHeight, true);
    }

    try {
        //this.joinButton.style.display = 'none';
        this.hangupButton.style.display = 'inline';

        trace('Starting call.');
        this.startTime = window.performance.now();

        this.peer = new Peer();
        await this.peer.connect(this.room);
        //const obj = JSON.stringify([this.peer.connect, this.room]);
        //this.worker.postMessage([this.peer, this.room]);

        this.peer.pc.ontrack = ({track, streams}) => {
            // once media for a remote track arrives, show it in the remote video element
            track.onunmute = () => {
                // don't set srcObject again if it is already set.
                if (this.remoteView.srcObject) return;
                console.log(streams);
                this.remoteView.srcObject = streams[0];
                trace('Remote peer connection received remote stream.');
                this.remoteView.play();
            };
        };

        const localStream = this.localView.srcObject;
        console.log('adding local stream');
        await this.peer.addLocalStream(localStream);

        await this.peer.waitMessage();

    } catch (err) {
        console.error(err);
    }
};

PeerUI.prototype.disconnect = async function() {
    await this.peer.disconnect();
    this.startButton.style.display = 'inline';
    //this.joinButton.style.display = 'inline';
    this.hangupButton.style.display = 'none';
    this.fullscreenButton.style.display = 'none';
    this.videoDiv.style.display = 'none';  

    trace('Ending call.');
    this.localView.srcObject.getVideoTracks()[0].stop();
    this.peerDiv.remove();
};

// Logs an action (text) and the time when it happened on the console.
function trace(text) {
  text = text.trim();
  const now = (window.performance.now() / 1000).toFixed(3);
  console.log(now, text);
}