var Peer = function(room, configuration, polite=true) {
    this.makingOffer = false;
    this.ignoreOffer = false;
    this.polite = polite;
    this.timeout = null;
};

Peer.prototype.connect = async function(room, configuration) {
    
    if (this.pc) {
        await this.disconnect();
    }
    
    if (!configuration) {
        configuration = {
          iceServers: [{urls: 'stun:stun.l.google.com:19302'}]
        };
    }
    
    pc = new RTCPeerConnection(configuration);
    signaling = new SignalingChannel(room);
    this.signaling = signaling;
    this.pc = pc;
    
    // send any ice candidates to the other peer
    pc.onicecandidate = async (event) => {
      if (event.candidate) {
        trace('Sending ICE candidate');
        console.log(event);
        event.candidate.type = 'candidate'
        await this.signaling.send(event.candidate);
      }
    }
    
    pc.oniceconnectionstatechange = (event) => {
      const peerConnection = event.target;
      trace(`ICE state change: ${peerConnection.iceConnectionState}.`);
    }
    
    // let the "negotiationneeded" event trigger offer generation
    pc.onnegotiationneeded = async () => {
      try {
        trace('making offer');
        this.makingOffer = true;
        await this.pc.setLocalDescription();
        await this.signaling.send(pc.localDescription);
      } catch (err) {
        console.error(err);
      } finally {
        this.makingOffer = false;
      }
    };
    
    // The perfect negotiation logic, separated from the rest of the application
    // from https://w3c.github.io/webrtc-pc/#perfect-negotiation-example
    
    this.signaling.onmessage = async (message) => {
      try {
        if (message == null) {
          return;
        }

        if (['offer', 'answer'].includes(message.type)) {
          const offerCollision = message.type == "offer" &&
                                (this.makingOffer || pc.signalingState != "stable");

          this.ignoreOffer = !this.polite && offerCollision;
          if (this.ignoreOffer) {
            return;
          }
          await pc.setRemoteDescription(message); // SRD rolls back as needed
          if (message.type == "offer") {
            await pc.setLocalDescription();
            await signaling.send(this.pc.localDescription);
            // The Python peer does not send candidates, so we do not expect more messages
            //clearTimeout(this.timeout);
          }
        } else if (message.type == 'candidate') {
          try {
            await pc.addIceCandidate(message);
          } catch (err) {
            if (!this.ignoreOffer) throw err; // Suppress ignored offer's candidates
          }
        } else if (message.type == 'bye') {
            await this.disconnect();
        }
          
        //if (onmessage) {
        //    onmessage(message);
        //}
          
      } catch (err) {
        console.error(err);
      }
    }
    
    const params = await this.signaling.connect();
    this.signalingParams = params;
    return pc;
};

Peer.prototype.addLocalStream = async function(localStream) {
    for (const track of localStream.getTracks()) {
        this.pc.addTrack(track, localStream);
        trace(`Adding device: ${track.label}.`);
    }
};

Peer.prototype.disconnect = async function() {
    clearTimeout(this.timeout);
    await this.signaling.close();

    if (this.pc) {
        await this.pc.close();
        this.pc = null;
    }
};

Peer.prototype.waitMessage = async function() {
    await this.signaling.receive();
    if (this.pc != null) {
        this.timeout = setTimeout(this.waitMessage, 1000);
    }
};

// Logs an action (text) and the time when it happened on the console.
function trace(text) {
  text = text.trim();
  const now = (window.performance.now() / 1000).toFixed(3);
  console.log(now, text);
}
