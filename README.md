# carim-discord-bot

A simple Discord bot that responds to a few basic commands
and has a RCon interface for BattlEye servers. It can also
establish cross chat between Discord and inside the game.

```
commands:
--help                displays this usage information
--hello               says hello to the beloved user
--random [num]        generate a random number between 0 and 100
                      or num if specified
--about               display some information about the bot

admin commands:
--command [command]        send command to the server, or list
                           the available commands
--safe_shutdown [seconds]  shutdown the server in a safe manner
                           with an optional delay
--schedule_status          show current scheduled item status
--kill                     make the bot terminate
--version                  display the current version of the bot
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

1. **WARNING** If updating from 1.0.1, be sure to backup your configuration.
   Unfortunately I made a mistake in saying to update the configuration file
   in the installed location. That file will be replaced during the update.
   Copy it someplace safe and then follow the setup instructions to fix.
1. Run `pip3 install carim-discord-bot -U`
1. Run `carim-bot --setup configuration` to see if any options have changed
1. Update your configuration file accordingly
1. Restart the service if you have one
