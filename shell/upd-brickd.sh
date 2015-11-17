echo 'Download latest brick daemon package'
wget http://download.tinkerforge.com/tools/brickd/linux/brickd_linux_latest_armhf.deb

echo 'installing new brick daemon'
dpkg -i brickd_linux_latest_armhf.deb

echo 'Done.'
