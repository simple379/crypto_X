from keep_alive import keep_alive
import telegram
from telegram.ext import Application, CommandHandler, ContextTypes
import httpx
import feedparser
import os
from datetime import datetime
from operator import itemgetter
import matplotlib.pyplot as plt
import io
import pandas as pd
import time
import asyncio
import threading
import logging

# --- Basic Configuration ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Environment & API Configuration ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '7972609552:AAHZvzeRP1B96Nezt0rFnCo54ahKMAiIVH4')
COINGECKO_API = "https://api.coingecko.com/api/v3"
ALTERNATIVE_API = "https://api.alternative.me"
NEWS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://decrypt.co/feed",
    "https://cryptopanic.com/news/public/?feed=rss"
]

# --- Rate Limiting & Caching ---
CACHE = {}
CACHE_EXPIRY = 180  # 3 minutes
API_SEMAPHORE = asyncio.Semaphore(5)  # Allow max 5 concurrent API requests
MAX_RETRIES = 3

# --- Common Coin Aliases ---
COIN_ALIASES = {
    'ton': 'the-open-network',
    'bnb': 'binancecoin',
    'shib': 'shiba-inu'
}

# --- Disclaimer ---
DISCLAIMER = """
⚠️ *CRYPTO RISK DISCLAIMER*
- Data from public sources only
- Not financial advice
- Markets are highly volatile
- Always do your own research (DYOR)
- Never invest more than you can afford to lose
"""

# --- Core Helper Functions ---

async def make_api_request(url: str, params: dict = None):
    """
    A robust, rate-limited, and retrying API request handler.
    """
    async with API_SEMAPHORE:
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, params=params, timeout=15)
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(f"Rate limit hit for {url}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"HTTP error for {url}: {e}")
                    return None
            except httpx.RequestError as e:
                logger.error(f"Request error for {url}: {e}")
                return None
    logger.error(f"API request failed for {url} after {MAX_RETRIES} retries.")
    return None

async def get_cached_data(key, func, *args, **kwargs):
    """Cache data to reduce API calls. Now supports async functions."""
    now = time.time()
    if key in CACHE and now - CACHE[key]['timestamp'] < CACHE_EXPIRY:
        return CACHE[key]['data']
    
    data = await func(*args, **kwargs)
    if data:
        CACHE[key] = {'data': data, 'timestamp': now}
    return data

async def _fetch_coins_list():
    """Internal function to fetch the coin list for caching."""
    return await make_api_request(f"{COINGECKO_API}/coins/list")

async def get_coin_id_from_symbol(symbol: str):
    """
    Get CoinGecko coin ID from a symbol, ID, or name.
    Handles common aliases.
    """
    query = symbol.lower()
    
    # Check aliases first
    if query in COIN_ALIASES:
        return COIN_ALIASES[query]

    coin_list = await get_cached_data("coins_list", _fetch_coins_list)
    if not coin_list:
        return None

    # Priority search: id -> symbol -> name
    for coin in coin_list:
        if coin['id'] == query:
            return coin['id']
    for coin in coin_list:
        if coin['symbol'] == query:
            return coin['id']
    for coin in coin_list:
        if coin['name'].lower() == query:
            return coin['id']
    return None

# --- Feature Functions ---

async def get_trending_coins():
    """Fetches the top 10 trending coins from CoinGecko asynchronously."""
    data = await make_api_request(f"{COINGECKO_API}/search/trending")
    if not data or 'coins' not in data:
        return "Could not retrieve trending coins at the moment."
    
    message = "🔥 **Top 10 Trending Coins** 🔥\n\n"
    for i, coin in enumerate(data['coins'][:10]):
        item = coin['item']
        message += (
            f"{i+1}. **{item['name']} ({item['symbol'].upper()})**\n"
            f"   - Rank: {item['market_cap_rank']}\n"
            f"   - Price (BTC): {item.get('price_btc', 0):.8f}\n\n"
        )
    return message

async def get_top_coins(limit=20):
    """Get top coins by market cap from CoinGecko asynchronously."""
    params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": limit, "page": 1, "sparkline": False}
    coins = await make_api_request(f"{COINGECKO_API}/coins/markets", params=params)
    if not coins:
        return "Could not retrieve top coins at the moment."

    message = "🏆 *Top 20 Cryptocurrencies by Market Cap* 🏆\n\n"
    for coin in coins:
        change_icon = "📈" if coin.get("price_change_percentage_24h", 0) >= 0 else "📉"
        message += (
            f"{coin.get('market_cap_rank', 'N/A')}. **{coin.get('name', 'N/A')} ({coin.get('symbol', '').upper()})**\n"
            f"   - Price: ${coin.get('current_price', 0):,.2f}\n"
            f"   - 24h Change: {change_icon} {coin.get('price_change_percentage_24h', 0):.2f}%\n"
            f"   - Market Cap: ${coin.get('market_cap', 0):,}\n\n"
        )
    return message

def get_crypto_news():
    """Fetches and combines news from multiple public RSS feeds."""
    all_entries = []
    for feed_url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                publish_time = entry.get('published_parsed', datetime.now().timetuple())
                all_entries.append({'title': entry.title, 'link': entry.link, 'source': feed.feed.title, 'published': datetime.fromtimestamp(time.mktime(publish_time))})
        except Exception as e:
            logger.error(f"Could not parse feed {feed_url}: {e}")
    
    if not all_entries:
        return "Could not retrieve crypto news at the moment."

    all_entries.sort(key=itemgetter('published'), reverse=True)
    message = "📰 **Latest Crypto News** 📰\n\n"
    for entry in all_entries[:10]:
        message += f"• [{entry['title']}]({entry['link']}) ({entry['source']})\n"
    return message

async def get_coin_price(symbol: str):
    """Fetches detailed price data for a specific coin asynchronously."""
    coin_id = await get_coin_id_from_symbol(symbol)
    if not coin_id:
        return f"❌ Could not find a coin with the symbol '{symbol.upper()}'."

    params = {"vs_currencies": "usd", "include_market_cap": "true", "include_24hr_vol": "true", "include_24hr_change": "true"}
    data = await make_api_request(f"{COINGECKO_API}/simple/price?ids={coin_id}", params=params)

    if not data or coin_id not in data:
        return f"❌ Could not retrieve price data for {symbol.upper()}. Please try again."

    coin_data = data[coin_id]
    price = coin_data.get('usd', 0)
    market_cap = coin_data.get('usd_market_cap', 0)
    vol_24h = coin_data.get('usd_24h_vol', 0)
    change_24h = coin_data.get('usd_24h_change', 0)
    change_emoji = "📈" if change_24h >= 0 else "📉"

    return (f"**{symbol.upper()} ({coin_id.capitalize()}) Price**\n\n"
            f"💰 **Price:** ${price:,.4f}\n"
            f"{change_emoji} **24h Change:** {change_24h:.2f}%\n"
            f"📊 **24h Volume:** ${vol_24h:,.2f}\n"
            f"🏦 **Market Cap:** ${market_cap:,.2f}\n")

async def get_historical_data(symbol: str, days=7):
    """Get historical price data for a chart asynchronously."""
    coin_id = await get_coin_id_from_symbol(symbol)
    if not coin_id:
        return None
        
    params = {"vs_currency": "usd", "days": str(days)}
    data = await make_api_request(f"{COINGECKO_API}/coins/{coin_id}/market_chart", params=params)
    
    if not data or "prices" not in data:
        return None
            
    prices = data["prices"]
    timestamps = [pd.to_datetime(p[0], unit='ms') for p in prices]
    values = [p[1] for p in prices]
    return {"timestamps": timestamps, "prices": values, "coin": symbol.upper()}

def generate_price_chart(historical_data):
    """Generate a price chart image."""
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5), facecolor='#1e1e1e')
    ax.set_facecolor('#1e1e1e')
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('grey')
    ax.spines['left'].set_color('grey')

    ax.plot(historical_data["timestamps"], historical_data["prices"], color='#007bff', linewidth=2)
    ax.set_title(f"{historical_data['coin']} {len(historical_data['timestamps']) > 1 and (historical_data['timestamps'][-1] - historical_data['timestamps'][0]).days}-Day Price Chart", color='white', fontsize=16)
    ax.set_xlabel("Date", color='grey')
    ax.set_ylabel("Price (USD)", color='grey')
    ax.grid(True, linestyle='--', alpha=0.2)
    ax.tick_params(axis='x', colors='grey')
    ax.tick_params(axis='y', colors='grey')
    fig.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), dpi=100)
    buf.seek(0)
    plt.close(fig)
    return buf

async def get_fear_and_greed_index():
    """Fetches the Crypto Fear & Greed Index asynchronously."""
    data = await make_api_request(f"{ALTERNATIVE_API}/fng/")
    if not data or 'data' not in data:
        return "Could not retrieve the Fear & Greed Index."

    value = int(data['data'][0]['value'])
    classification = data['data'][0]['value_classification']
    
    emoji = {"Extreme Fear": "😱", "Fear": "😨", "Neutral": "😐", "Greed": "😊", "Extreme Greed": "🤑"}.get(classification, "🤔")
    meter = "[" + "🟩" * (value // 10) + "⬜️" * (10 - value // 10) + "]"

    return (f"{emoji} **Crypto Fear & Greed Index**\n\n"
            f"Current Value: `{value}` - *{classification}*\n"
            f"{meter}\n\n"
            "0-24: Extreme Fear\n25-44: Fear\n45-54: Neutral\n"
            "55-74: Greed\n75-100: Extreme Greed")

# --- Telegram Command Handlers ---

async def start_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (f"👋 *Welcome to Crypto Guru!* 👋\n"
               f"Your personal cryptocurrency market assistant.\n\n"
               f"{DISCLAIMER}")
    await update.message.reply_text(welcome, parse_mode='Markdown')
    await help_command(update, context)

async def help_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = ("*Available Commands:*\n"
                 "/start - Show welcome message\n"
                 "/trending - Top 10 trending coins\n"
                 "/top - Top 20 coins by market cap\n"
                 "/price `<coin>` - Current price of a coin\n"
                 "/price7d `<coin>` - 7-day price chart\n"
                 "/news - Latest crypto news\n"
                 "/feargreed - Fear & Greed Index")
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def trending_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    message = await get_cached_data("trending", get_trending_coins)
    await update.message.reply_text(message, parse_mode='Markdown')

async def top_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    message = await get_cached_data("top_coins", get_top_coins)
    await update.message.reply_text(message, parse_mode='Markdown')

async def news_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    message = await asyncio.to_thread(get_crypto_news)
    await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)

async def price_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ℹ️ Please specify a coin symbol. Example: `/price btc`")
        return
    coin_symbol = context.args[0]
    message = await get_coin_price(coin_symbol)
    await update.message.reply_text(message, parse_mode='Markdown')

async def price7d_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ℹ️ Please specify a coin. Example: `/price7d btc`")
        return
    coin_symbol = context.args[0]
    await update.message.reply_text(f"⏳ Generating chart for {coin_symbol.upper()}...")
    
    historical_data = await get_historical_data(coin_symbol, days=7)
    
    if not historical_data:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Couldn't get historical data for {coin_symbol.upper()}. The API might be busy or the symbol is incorrect. Please try again.")
        return
        
    chart_buf = await asyncio.to_thread(generate_price_chart, historical_data)
    await update.message.reply_photo(photo=chart_buf, caption=f"7-day price chart for {coin_symbol.upper()}", parse_mode='Markdown')

async def feargreed_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    message = await get_cached_data("fear_greed", get_fear_and_greed_index)
    await update.message.reply_text(message, parse_mode='Markdown')

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

async def post_init(application: Application):
    """Actions to run after the bot is initialized."""
    await application.bot.set_my_commands([
        ('start', 'Start the bot'),
        ('trending', 'See trending coins'),
        ('top', 'See top coins by market cap'),
        ('price', 'Get price for a specific coin'),
        ('price7d', 'Get 7-day price chart for a coin'),
        ('news', 'Get latest crypto news'),
        ('feargreed', 'Check the Fear & Greed Index'),
        ('help', 'Show this help message'),
    ])

def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == 'YOUR_FALLBACK_TOKEN_HERE':
        logger.critical("TELEGRAM_BOT_TOKEN is not set. Please set it as an environment variable.")
        return

    builder = Application.builder().token(TELEGRAM_BOT_TOKEN)
    builder.post_init(post_init)
    application = builder.build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("trending", trending_command))
    application.add_handler(CommandHandler("top", top_command))
    application.add_handler(CommandHandler("news", news_command))
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("price7d", price7d_command))
    application.add_handler(CommandHandler("feargreed", feargreed_command))
    
    application.add_error_handler(error_handler)

    logger.info("Crypto Guru bot is starting...")
    
    try:
        application.run_polling()
    except Exception as e:
        logger.critical(f"Bot failed to start: {e}")

if __name__ == '__main__':
    keep_alive_thread = threading.Thread(target=keep_alive)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()
    
    main()
