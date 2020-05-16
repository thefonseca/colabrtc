#!/bin/bash

export DEBIAN_FRONTEND=noninteractive

echo 'Cloning repository https://github.com/alievk/avatarify.git...'
git clone -q https://github.com/alievk/avatarify.git
cd avatarify && git reset -q --hard 27596677163b2fa86e97b57bcc20088872c1d05a

echo 'Downloading model checkpoints from repository https://www.dropbox.com/s/t7h24l6wx9vreto/vox-adv-cpk.pth.tar?dl=1...'
wget -q -O vox-adv-cpk.pth.tar https://www.dropbox.com/s/t7h24l6wx9vreto/vox-adv-cpk.pth.tar?dl=1

pip -q install face-alignment pyfakewebcam < /dev/null > /dev/null

# FOMM
echo 'Installing FOMM submodule...'
cd /content/avatarify && git submodule update -q --init
cd /content/avatarify && pip -q install -r fomm/requirements.txt < /dev/null > /dev/null
pip -q install requests < /dev/null > /dev/null

echo 'Avatarify setup complete!'