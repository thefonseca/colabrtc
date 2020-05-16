async function invoke_python(room, action, args) {
  // trace('Calling remote function: ' + room + '.colab.signaling.' + action);
  const result = await google.colab.kernel.invokeFunction(
    room + '.colab.signaling.' + action, // The callback name.
    args, // The arguments.
    {}); // kwargs

  let json = null;
  if ('application/json' in result.data) {
      json = result.data['application/json'];
      console.log('Result from python:')  
      console.log(json);
  }
  return json;
}

var SignalingChannel = function(room) {
  this.room = room;

  // Public callbacks. Keep it sorted.
  this.onerror = null;
  this.onmessage = null;
};

SignalingChannel.prototype.send = async function(message) {
  await invoke_python(this.room, 'send', [JSON.stringify(message)]);
};

SignalingChannel.prototype.receive = async function() {
  const message = await invoke_python(this.room, 'receive', []);
  if (this.onmessage) {
    this.onmessage(message);
  }
  return message;
};

SignalingChannel.prototype.connect = async function() {
  return await invoke_python(this.room, 'connect', []);
};

SignalingChannel.prototype.close = async function() {
  return await invoke_python(this.room, 'close', []);
};