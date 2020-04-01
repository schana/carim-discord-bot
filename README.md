# carim-discord-bot

Set up a google cloud instance, and then
```shell script
sudo apt install git
sudo apt install python3-pip

git clone https://github.com/schana/carim-discord-bot.git
cd carim-discord-bot
sudo python3 setup.py install

sudo mkdir /etc/carim
sudo nano /etc/carim/token.txt
# copy in your discord token
sudo chmod 755 /etc/carim
sudo chmod 640 /etc/carim/token.txt

sudo cp carim.service /etc/systemd/system/
sudo systemctl enable carim.service
sudo systemctl start carim.service
```

When you make updates
```shell script
cd carim-discord-bot
git reset HEAD --hard
sudo python3 setup.py install
sudo systemctl restart carim.service
```