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
    }

    //localView.addEventListener('loadedmetadata', logVideoLoaded);
    remoteView.addEventListener('loadedmetadata', logVideoLoaded);
    //remoteView.addEventListener('onresize', logResizedVideo);

    // Define action buttons.
    const controlDiv = document.createElement('div');
    controlDiv.style.textAlign = 'center';
    const startButton = document.createElement('button');
    //const joinButton = document.createElement('button');
    const hangupButton = document.createElement('button');
    startButton.textContent = 'Start';
    //joinButton.textContent = 'Join';
    hangupButton.textContent = 'Hangup';
    controlDiv.appendChild(startButton);
    //controlDiv.appendChild(joinButton);
    controlDiv.appendChild(hangupButton);
    
    // Set up initial action buttons status: disable call and hangup.
    //callButton.disabled = true;
    hangupButton.style.display = 'none';
    
    peerDiv.appendChild(videoDiv);
    peerDiv.appendChild(controlDiv);
    
    this.localView = localView;
    this.remoteView = remoteView;
    this.peerDiv = peerDiv;
    this.videoDiv = videoDiv;
    this.startButton = startButton;
    //this.joinButton = joinButton;
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
    
    // Add click event handlers for buttons.
    this.startButton.addEventListener('click', start);
    //this.joinButton.addEventListener('click', join);
    this.hangupButton.addEventListener('click', hangup);
    
//     const workerCode = () => {
//         onmessage = async function(e) {
//             //const data = JSON.parse(e.data);
//             console.log(e.data);
//             console.log(e.data[0].connect);
//             const [async_fn, ...args] = e.data;
//             await async_fn(...args);
//             //self.postMessage('msg from worker');
//         };
//     }
//     const workerCodeStr = workerCode.toString().replace(/^[^{]*{\s*/,'').replace(/\s*}[^}]*$/,'');
//     console.log(workerCodeStr);
//     const workerBlob = new Blob([workerCodeStr], { type: "text/javascript" })
//     this.worker = new Worker(window.URL.createObjectURL(workerBlob));
};


PeerUI.prototype.connect = async function(room) {
    //startButton.disabled = true;
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    this.localView.srcObject = stream;
    this.localView.play();
    trace('Received local stream.');

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
    this.videoDiv.style.display = 'none';  

    trace('Ending call.');
    this.localView.srcObject.getVideoTracks()[0].stop();
};

// Logs an action (text) and the time when it happened on the console.
function trace(text) {
  text = text.trim();
  const now = (window.performance.now() / 1000).toFixed(3);
  console.log(now, text);
}