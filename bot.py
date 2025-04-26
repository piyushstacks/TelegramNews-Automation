import os
import logging
import requests
import google.generativeai as genai
import pytz
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# API Keys
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
SERP_API_KEY = os.getenv('SERP_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Initialize the model with Gemini 2.5 Pro
model = genai.GenerativeModel('gemini-2.5-pro-exp-03-25')

# Configure the model settings
generation_config = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 40,
    "max_output_tokens": 2048,
}

# News sources and categories
NEWS_SOURCES = ['bbc-news', 'cnn', 'the-verge', 'wired', 'the-wall-street-journal']
NEWS_CATEGORIES = ['technology', 'politics', 'business', 'science']

# Function to fetch news from NewsAPI
def fetch_news_from_newsapi():
    articles = []
    priority_categories = ['technology', 'politics']
    
    # Fetch priority categories first (technology and politics)
    for category in priority_categories:
        url = f"https://newsapi.org/v2/top-headlines?category={category}&language=en&apiKey={NEWS_API_KEY}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data.get('articles'):
                articles.extend([{
                    **article,
                    'category': category.capitalize()
                } for article in data['articles'][:5]])  # Get top 5 articles from priority categories
    
    # Fetch by sources
    for source in NEWS_SOURCES:
        url = f"https://newsapi.org/v2/top-headlines?sources={source}&apiKey={NEWS_API_KEY}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data.get('articles'):
                articles.extend([{
                    **article,
                    'category': 'General'
                } for article in data['articles'][:3]])  # Get top 3 articles from each source
    
    # Fetch remaining categories
    remaining_categories = [cat for cat in NEWS_CATEGORIES if cat not in priority_categories]
    for category in remaining_categories:
        url = f"https://newsapi.org/v2/top-headlines?category={category}&language=en&apiKey={NEWS_API_KEY}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data.get('articles'):
                articles.extend([{
                    **article,
                    'category': category.capitalize()
                } for article in data['articles'][:3]])  # Get top 3 articles from each category
    
    # Remove duplicates based on title
    unique_articles = []
    titles = set()
    for article in articles:
        if article['title'] not in titles:
            titles.add(article['title'])
            unique_articles.append(article)
    
    return unique_articles  # Return all unique articles

# Function to fetch news from SERP API (as a backup)
def fetch_news_from_serpapi():
    url = f"https://serpapi.com/search.json?q=latest+news&tbm=nws&api_key={SERP_API_KEY}"
    response = requests.get(url)
    articles = []
    
    if response.status_code == 200:
        data = response.json()
        if 'news_results' in data:
            for item in data['news_results'][:10]:
                articles.append({
                    'title': item.get('title', ''),
                    'description': item.get('snippet', ''),
                    'url': item.get('link', ''),
                    'source': item.get('source', '')
                })
    
    return articles

# Function to summarize news using Gemini
def summarize_news(articles):
    if not articles:
        return "No news articles found today."
    
    # Group articles by category
    categorized_articles = {}
    for article in articles:
        category = article.get('category', 'General')
        if category not in categorized_articles:
            categorized_articles[category] = []
        categorized_articles[category].append(article)
    
    # Create a prompt for Gemini with organized sections
    today = datetime.now().strftime("%B %d, %Y")
    prompt = f"Create a daily news digest with the following format:\n\n"
    prompt += f"Hello Master, your daily news digest - {today}\n\n"
    prompt += "Format the digest with these rules:\n"
    prompt += "1. Use clear section headers with emoji indicators\n"
    prompt += "2. Present each news item as a bullet point (•)\n"
    prompt += "3. Add a blank line between sections and news items\n"
    prompt += "4. Keep summaries concise (2-3 sentences)\n\n"
    
    # Add priority categories first
    for priority_category in ['Technology', 'Politics']:
        if priority_category in categorized_articles:
            prompt += f"\n📌 {priority_category} News\n\n"
            for article in categorized_articles[priority_category]:
                prompt += f"• {article['title']}\n"
                prompt += f"  {article.get('description', 'No description')}\n"
                prompt += f"  Source: {article.get('source', {}).get('name', article.get('source', 'Unknown'))}\n\n"
            del categorized_articles[priority_category]
    
    # Add remaining categories
    if categorized_articles:
        prompt += "\n📰 Other Important Updates\n\n"
        for category, articles in categorized_articles.items():
            for article in articles:
                prompt += f"• [{category}] {article['title']}\n"
                prompt += f"  {article.get('description', 'No description')}\n"
                prompt += f"  Source: {article.get('source', {}).get('name', article.get('source', 'Unknown'))}\n\n"
    
    # Generate summary with Gemini
    try:
        response = model.generate_content(prompt)
        summary = response.text
        
        # Add footer with hashtags
        footer = f"\n\n#DailyNews #TechNews #PoliticsNews #GlobalUpdates"
        
        return summary + footer
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return f"Failed to generate summary: {str(e)}"

# Function to chunk long messages
def chunk_message(text, max_length=4000):
    chunks = []
    current_chunk = ""
    
    # Split by newlines to preserve formatting
    lines = text.split('\n')
    
    for line in lines:
        if len(current_chunk) + len(line) + 1 <= max_length:
            current_chunk += line + '\n'
        else:
            chunks.append(current_chunk.strip())
            current_chunk = line + '\n'
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

# Function to send news digest to Telegram channel
async def send_news_digest(context: ContextTypes.DEFAULT_TYPE):
    try:
        # Fetch news
        articles = fetch_news_from_newsapi()
        
        # If NewsAPI fails, try SERP API as backup
        if not articles:
            logger.info("NewsAPI returned no results, trying SERP API")
            articles = fetch_news_from_serpapi()
        
        # Summarize news
        digest = summarize_news(articles)
        
        # Split digest into chunks if it's too long
        message_chunks = chunk_message(digest)
        
        # Send each chunk with appropriate formatting
        for i, chunk in enumerate(message_chunks):
            try:
                # Only use Markdown for the first chunk to avoid header formatting issues
                parse_mode = 'Markdown' if i == 0 else None
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=chunk,
                    parse_mode=parse_mode
                )
                logger.info(f"Chunk {i+1}/{len(message_chunks)} sent successfully")
            except Exception as chunk_error:
                logger.error(f"Error sending chunk {i+1}: {chunk_error}")
                # Try sending without parse_mode if parsing fails
                if parse_mode:
                    try:
                        await context.bot.send_message(
                            chat_id=CHANNEL_ID,
                            text=chunk
                        )
                        logger.info(f"Chunk {i+1} sent successfully without parsing")
                    except Exception as retry_error:
                        logger.error(f"Failed to send chunk {i+1} even without parsing: {retry_error}")
                        continue
        
        logger.info("News digest sent successfully")
    except Exception as e:
        logger.error(f"Error in send_news_digest: {e}")
        # Notify about the error
        try:
            error_message = f"⚠️ Error sending news digest: {str(e)}"
            await context.bot.send_message(chat_id=CHANNEL_ID, text=error_message)
        except:
            logger.error("Failed to send error notification")

# Command handler for manual trigger
async def send_digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Generating and sending news digest...")
    await send_news_digest(context)
    await update.message.reply_text("News digest sent!")

# Command handler for start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to the News Automation Bot!\n\n"
        "This bot automatically sends daily news digests to the configured channel.\n"
        "Use /senddigest to manually trigger a news digest.\n"
        "Use /help to see all available commands."
    )

# Command handler for help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Available commands:\n\n"
        "/start - Start the bot\n"
        "/senddigest - Manually send a news digest\n"
        "/help - Show this help message"
    )

# Setup scheduler
def setup_scheduler(application):
    scheduler = BackgroundScheduler(timezone=pytz.timezone('UTC'))
    
    # Schedule the job to run daily at 8:00 AM UTC
    scheduler.add_job(
        lambda: application.create_task(send_news_digest(application)),
        'cron',
        hour=8,
        minute=0
    )
    
    scheduler.start()
    logger.info("Scheduler started, will send digest daily at 8:00 AM UTC")

def main():
    # Create the Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("senddigest", send_digest_command))

    # Setup scheduler
    setup_scheduler(application)

    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()