# carim-discord-bot

A simple Discord bot that can communicate with BattlEye via RCon. Support can be found
in the [Carim Discord](https://discord.gg/kdPnVu4).

Table of Contents
* [Install](#install)
* [Update](#update)
* [Features](#features)
* [Usage](#usage)
  + [Examples](#examples)
* [Scheduled Commands](#scheduled-commands)
  + [Examples](#examples-1)

## Install

1. Install Python 3.7 or 3.8
1. Run `pip3 install carim-discord-bot`
1. Run `carim-bot --setup` and follow the instructions

Alternatively, you can [deploy using Heroku](https://github.com/schana/carim-discord-bot-heroku).

## Update

1. Run `pip3 install carim-discord-bot -U`
1. Run `carim-bot --setup configuration` to see if any options have changed
1. Update your configuration file accordingly
1. Restart the service if you have one

## Features

* Log RCon communication to Discord
* Send RCon commands to the server via Discord
* Schedule RCon commands to be executed by relative time or aligned with the clock
* Skip the next instance of a scheduled command
* Perform safe shutdowns of the server, including kicking players and locking
* Establish cross-chat that links the in-game chat and a Discord channel

## Usage

```
commands:
--help                     displays this usage information
--about                    display some information about the bot
--version                  display the current version of the bot

admin commands:
--command [command]        send command to the server, or list
                           the available commands
--shutdown [seconds]       shutdown the server in a safe manner
                           with an optional delay; notice messages
                           are broadcasted to the server at
                           60, 30, 20, 10, 5, 4, 3, 2, and 1 minute
                           until shutdown
--status                   show current scheduled item status
--skip index               skip next run of scheduled command
--kill                     make the bot terminate
```

### Examples

```
--command "say -1 Hello everybody!"
# this sends a message to everybody on the server
# notice the quotes around the command

--command players
# gets a list of currently connected players

--shutdown 3600
# schedules the server to be shutdown in an hour
```

## Scheduled Commands

### Examples

Send a global server message every 5 minutes
```json
{
  "command": "say -1 Hello everybody!",
  "interval": 300
}
```

Shutdown the server every 3 hours starting at 00:00
```json
{
  "command": "safe_shutdown",
  "delay": 3600,
  "interval": 10800,
  "with_clock": true,
  "offset": 3600
}
```
