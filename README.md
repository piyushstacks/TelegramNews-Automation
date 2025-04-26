# Telegram News Automation Bot

This bot automatically fetches news from various sources, summarizes them using Google's Gemini AI, and posts daily digests to a Telegram channel.

## Features

- Fetches news from multiple sources via NewsAPI
- Uses SERP API as a backup news source
- Summarizes news using Google's Gemini AI
- Posts daily digests to a configured Telegram channel
- Scheduled to run automatically every day at 8:00 AM UTC
- Supports manual triggering of news digests

## Setup

### Prerequisites

- Python 3.8 or higher
- A Telegram Bot Token (get from [@BotFather](https://t.me/botfather))
- A Telegram Channel ID where the bot will post updates
- NewsAPI Key (get from [NewsAPI.org](https://newsapi.org))
- SERP API Key (optional, get from [SerpAPI](https://serpapi.com))
- Google Gemini API Key (get from [Google AI Studio](https://makersuite.google.com/app/apikey))

### Installation

1. Clone this repository
2. Install the required packages:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on the provided `.env.example`:

```bash
cp .env.example .env
```

4. Edit the `.env` file and add your API keys and configuration

### Running the Bot

To start the bot:

```bash
python bot.py
```

## Usage

Once the bot is running, it will automatically post news digests to your configured Telegram channel every day at 8:00 AM UTC.

You can also interact with the bot directly:

- `/start` - Start the bot
- `/help` - Show available commands
- `/senddigest` - Manually trigger a news digest

## Customization

You can customize the news sources and categories by modifying the `NEWS_SOURCES` and `NEWS_CATEGORIES` variables in the `bot.py` file.

## Deployment

For 24/7 operation, deploy the bot to a cloud service like:

- Heroku
- AWS
- Google Cloud
- DigitalOcean

Make sure to set up the environment variables on your hosting platform.

## License

MIT