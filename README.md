# Telegram Chat Statistics Bot

This script is a Telegram bot that collects and provides chat statistics when you send the `/stats` command in a private chat with the bot.

## Features

The bot provides the following statistics:

*   **Total Messages:** Displays the total number of messages in the chat.
*   **User Message Counts and Reply Ratios:**
    *   Lists each user in the chat.
    *   Shows the number of messages sent by each user.
    *   Calculates and displays the reply ratio between users in the chat. This ratio shows how often one user replies to another.
*   **Top Messages:** Shows a list of top message days based on the quantity of messages.
    *   Each entry shows the date of the top message day and the corresponding message count on that day.
*   **Maximum Conversation Time:** Calculates and displays the maximum time spent in conversations within the chat.
    *   It provides two time values:
        *   **Detailed:** A more detailed calculation of the maximum conversation time.
        *   **Brief:** A more summarized calculation of the maximum conversation time.

## How to Use

1.  **Start a Private Chat with the Bot:** Initiate a private chat with your Telegram bot.
2.  **Send the `/stats` Command:**  Type `/stats` in the chat and send the message.
3.  **View the Statistics:** The bot will reply with a message containing the statistics outlined above.


## Technical Details

The script uses the following:

*   [Pyrogram](https://github.com/TelegramPlayGround/pyrogram) - A Python library for interacting with the Telegram API.

## Requirements

*   Python 3.7 or higher
*   Pyrogram library
*   A Telegram bot token

## Setup Instructions
1. Make sure you have python 3.7 or higher
2. Install the required libraries: `pip install pyrotgfork`
3. Create a `config.py` file in the same folder as your script and paste your telegram API id and api hash in the file like this:
API_HASH = "some_hash"
API_ID = "some_id"
LANGUAGE = "en"
