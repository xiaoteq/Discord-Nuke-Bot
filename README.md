# Discord Nuke Bot

A powerful Discord nuke bot.

## Support

~~Join our Discord server for support and updates: [Discord Link](https://discord.gg)~~

## Features

- Delete/Create roles
- Delete/Create channels
- Delete/Change server icon
- Delete/Change server name
- Delete/Change server banner (planned)
- Delete stickers
- Delete emojis
- Delete server templates
- Disable Verification Level
- Disable Content Filter
- Disable System Channel
- Enable All Notifications
- Send messages (webhook+bot with tts)
- Create category (planned)
- Ban other bots
- Give @everyone admin permission

- Use Proxy (planned)


## Installation

```bash
pip install requirements.txt
```

## Configuration

1. `config.json` file:

```python
channel_name = "CHANNEL_NAME"
role_name = "ROLE_NAME"
server_name = "SERVER_NAME"
webhook_name = "WEBHOOK_NAME"
message = "MESSAGE"
```

2. `.env` file:

```
TOKEN = "Your Bot Token"
```

## Usage

1. Run the bot:
```bash
python main.py
```

2. Use command in bot DM:

```
!nuke server_id
```

## Notes

- Please check the bot has admin permissions in the target server
- Move the bot's role as high as possible in the role list
- Use lowercase when setting channel names

## Disclaimer

This project is for educational purposes only. Use at your own risk. Users are responsible for complying with all applicable laws and terms of service.
