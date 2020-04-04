# carim-discord-bot

A simple Discord bot that responds to a few basic commands
that also has a RCon interface for BattlEye servers. It also
has the capability to link a discord channel to the server chat.

```
usage: [--help] [--hello] [--random [RANDOM]]

optional arguments:
--help              displays this usage information
--hello             says hello to the beloved user
--random [RANDOM]   generate a random number between 0 and
                    RANDOM (default: 100)

admin arguments:
--command [COMMAND] sends COMMAND to RCon server; if COMMAND
                    is blank, list the available commands
                    COMMAND must be enclosed by quotes ("")
                    if it contains spaces
--kill              kills the bot
```

Example:
```
--command "say -1 Hello everybody!"

# this sends a message to everybody on the server
```


## Setup

Instructions for Debian
```shell script
sudo apt install git
sudo apt install python3-pip

git clone https://github.com/schana/carim-discord-bot.git
cd carim-discord-bot
sudo python3 setup.py install

sudo mkdir /etc/carim
sudo cp carim.json /etc/carim
# edit /etc/carim/carim.json
# token:                your discord bot token
# rcon_ip:              ip address of your rcon server
# rcon_port:            port of your rcon server
# rcon_password:        rcon password
# rcon_publish_channel: discord channel id that events
#                       should be published to
# rcon_admin_channels:  list of discord channel ids that
#                       can issue admin commands to the bot
# rcon_chat_channel:    channel id for linking discord and
#                       server-side chats
# rcon_count_channel:   channel id that bot will update with
#                       the current number of players online
#                       (I use a category for this)
sudo chmod 755 /etc/carim
sudo chmod 640 /etc/carim/carim.json

sudo cp carim.service /etc/systemd/system/
sudo systemctl enable carim.service
sudo systemctl start carim.service
```

To install updates
```shell script
cd carim-discord-bot
git reset HEAD --hard
sudo python3 setup.py install
sudo systemctl restart carim.service
```