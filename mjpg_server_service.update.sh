pathSelf=$(realpath $(dirname $0))
pathLink=/usr/local/bin/mjpg_server.py

# Make a link in a known directory so the service knows where to point

rm $pathLink
ln -s $pathSelf/mjpg_server.py $pathLink

# Copy service definition into system directory

cp $pathSelf/mjpg_server.service /etc/systemd/system

# Refresh systemctl to know about the updated service definition

systemctl daemon-reload

# Restart the service

systemctl restart mjpg_server.service

# Show processes for confirmation

ps -ef | grep mjpg_server.py | grep -v grep