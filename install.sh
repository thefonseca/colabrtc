#!/bin/bash

export DEBIAN_FRONTEND=noninteractive

echo 'Updating ffmpeg...'
# We need this to update ffmpeg to version 4.x
add-apt-repository -qy ppa:savoury1/ffmpeg4 > /dev/null 2>&1
apt-get -qq install ffmpeg < /dev/null > /dev/null

echo 'Installing dependencies...'
apt-get -qq install libavdevice-dev libavfilter-dev libopus-dev libvpx-dev \
 pkg-config libsrtp2-dev libavformat-dev libavcodec-dev libavutil-dev \
 libswscale-dev libswresample-dev  < /dev/null > /dev/null

pip -qq install -r /content/colabrtc/requirements.txt < /dev/null > /dev/null

echo 'ColabRTC setup complete!'