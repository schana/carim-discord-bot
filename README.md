# carim-discord-bot

A simple Discord bot that responds to a few basic commands
and has a RCon interface for BattlEye servers. It can also
establish cross chat between Discord and inside the game.

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

Examples:
```
--command "say -1 Hello everybody!"
# this sends a message to everybody on the server
# notice the quotes around the command

--command players
# gets a list of currently connected players
```


## Setup

Instructions for Debian Buster
```shell script
sudo apt install git
sudo apt install python3-pip

git clone https://github.com/schana/carim-discord-bot.git
cd carim-discord-bot
sudo python3 setup.py install

sudo mkdir /etc/carim
sudo cp carim.json /etc/carim
sudo nano /etc/carim/carim.json # insert your values
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
git pull
sudo python3 setup.py install
sudo systemctl restart carim.service
```