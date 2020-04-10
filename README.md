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
--version           prints the version of the bot
```

Examples:
```
--command "say -1 Hello everybody!"
# this sends a message to everybody on the server
# notice the quotes around the command

--command players
# gets a list of currently connected players
```


## Install

1. Install Python 3.7 or 3.8
1. Run `pip3 install carim-discord-bot`
1. Run `carim-bot --setup` and follow the instructions

## Update

1. Run `pip3 install carim-discord-bot -U`
1. Run `carim-bot --setup configuration` to see if any options have changed
1. Update your configuration file accordingly
1. Restart the service if you have one
