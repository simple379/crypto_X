from telegram.ext import Application, CommandHandler, ContextTypes
import telegram
import requests
import feedparser
import os
from datetime import datetime
from operator import itemgetter
import matplotlib.pyplot as plt
import io
import pandas as pd
import time
import logging
import sys

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '7972609552:AAHZvzeRP1B96Nezt0rFnCo54ahKMAiIVH4')

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# --- Data Sources & APIs ---
NEWS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://decrypt.co/feed",
    "https://cryptopanic.com/news/public/?feed=rss"
]
COINGECKO_API = "https://api.coingecko.com/api/v3"
ALTERNATIVE_API = "https://api.alternative.me"

# --- Global Cache ---
CACHE = {}
CACHE_EXPIRY = 300  # 5 minutes

# --- Disclaimer ---
DISCLAIMER = """
⚠️ *CRYPTO RISK DISCLAIMER*
- Data from public sources only
- Not financial advice
- Markets are highly volatile
- Always do your own research (DYOR)
- Never invest more than you can afford to lose
"""

# --- Helper Functions ---

def get_cached_data(key, func, *args, **kwargs):
    """Cache data to reduce API calls."""
    now = time.time()
    if key in CACHE and now - CACHE[key]['timestamp'] < CACHE_EXPIRY:
        return CACHE[key]['data']
    
    data = func(*args, **kwargs)
    CACHE[key] = {'data': data, 'timestamp': now}
    return data

def get_coin_id_from_symbol(symbol: str):
    """Get CoinGecko coin ID from a symbol with enhanced reliability."""
    symbol = symbol.lower()
    
    # Try to get coin list from cache or API
    try:
        coin_list = get_cached_data("coins_list", lambda: requests.get(
            f"{COINGECKO_API}/coins/list", 
            timeout=10
        ).json())
    except Exception as e:
        logger.error(f"Error fetching coin list: {e}")
        return None
    
    # Handle API error responses
    if not isinstance(coin_list, list):
        logger.error(f"Unexpected coin list response: {coin_list}")
        return None
    
    # Search for matching symbol
    for coin in coin_list:
        if isinstance(coin, dict) and 'symbol' in coin and coin['symbol'] == symbol:
            return coin['id']
    
    return None

def get_trending_coins():
    """Fetches the top 10 trending coins from CoinGecko."""
    try:
        url = f"{COINGECKO_API}/search/trending"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'coins' in data:
            message = "🔥 **Top 10 Trending Coins** 🔥\n\n"
            for i, coin in enumerate(data['coins'][:10]):
                item = coin['item']
                message += (
                    f"{i+1}. **{item['name']} ({item['symbol']})**\n"
                    f"   - Rank: {item['market_cap_rank']}\n"
                    f"   - Price (BTC): {item['price_btc']:.8f}\n\n"
                )
            return message
        return "Could not retrieve trending coins."
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching trending coins: {e}")
        return "An error occurred while fetching trending coins."

def get_top_coins(limit=20):
    """Get top coins by market cap from CoinGecko."""
    try:
        params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": limit, "page": 1, "sparkline": False}
        response = requests.get(f"{COINGECKO_API}/coins/markets", params=params, timeout=10)
        response.raise_for_status()
        coins = response.json()
        
        message = "🏆 *Top 20 Cryptocurrencies by Market Cap* 🏆\n\n"
        for coin in coins:
            change_icon = "📈" if coin.get("price_change_percentage_24h", 0) >= 0 else "📉"
            message += (
                f"{coin['market_cap_rank']}. **{coin['name']} ({coin['symbol'].upper()})**\n"
                f"   - Price: ${coin['current_price']:,.2f}\n"
                f"   - 24h Change: {change_icon} {coin['price_change_percentage_24h']:.2f}%\n"
                f"   - Market Cap: ${coin['market_cap']:,}\n\n"
            )
        return message
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting top coins: {e}")
        return "An error occurred while fetching top coins."

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
            continue

    if not all_entries:
        return "Could not retrieve crypto news at the moment."

    all_entries.sort(key=itemgetter('published'), reverse=True)
    message = "📰 **Latest Crypto News** 📰\n\n"
    for entry in all_entries[:8]:
        message += f"• [{entry['title']}]({entry['link']}) ({entry['source']})\n"
    return message

def get_coin_price(symbol: str):
    """Fetches detailed price data for a specific coin with enhanced error handling."""
    if not symbol:
        return "Please provide a coin symbol. Example: `/price btc`"
        
    coin_id = get_coin_id_from_symbol(symbol)
    if not coin_id:
        return f"Could not find a coin with the symbol '{symbol}'."

    try:
        url = f"{COINGECKO_API}/simple/price?ids={coin_id}&vs_currencies=usd&include_market_cap=true&include_24hr_vol=true&include_24hr_change=true"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if coin_id not in data:
            return f"Could not find data for '{coin_id}'. Please use the coin's ID from CoinGecko."

        coin_data = data[coin_id]
        price = coin_data.get('usd', 0)
        market_cap = coin_data.get('usd_market_cap', 0)
        vol_24h = coin_data.get('usd_24h_vol', 0)
        change_24h = coin_data.get('usd_24h_change', 0)
        change_emoji = "📈" if change_24h >= 0 else "📉"

        return (f"**{coin_id.capitalize()} Price**\n\n"
                f"💰 **Price:** ${price:,.4f}\n"
                f"{change_emoji} **24h Change:** {change_24h:.2f}%\n"
                f"📊 **24h Volume:** ${vol_24h:,.2f}\n"
                f"🏦 **Market Cap:** ${market_cap:,.2f}\n")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching coin price for {coin_id}: {e}")
        return f"An error occurred while fetching price data for {coin_id}."
    except Exception as e:
        logger.error(f"Unexpected error in get_coin_price: {e}")
        return "An unexpected error occurred. Please try again later."

def get_historical_data(symbol: str, days=7):
    """Get historical price data for a chart."""
    coin_id = get_coin_id_from_symbol(symbol)
    if not coin_id:
        return None
        
    try:
        params = {"vs_currency": "usd", "days": days}
        response = requests.get(f"{COINGECKO_API}/coins/{coin_id}/market_chart", params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("prices"):
            return None
            
        prices = data["prices"]
        timestamps = [pd.to_datetime(p[0], unit='ms') for p in prices]
        values = [p[1] for p in prices]
        return {"timestamps": timestamps, "prices": values, "coin": symbol.upper()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting historical data for {coin_id}: {e}")
        return None

def generate_price_chart(historical_data):
    """Generate a price chart image."""
    plt.figure(figsize=(10, 5))
    plt.plot(historical_data["timestamps"], historical_data["prices"], color='#007bff')
    plt.title(f"{historical_data['coin']} 7-Day Price Chart")
    plt.ylabel("Price (USD)")
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

def get_fear_and_greed_index():
    """Fetches the Crypto Fear & Greed Index."""
    try:
        response = requests.get(f"{ALTERNATIVE_API}/fng/", timeout=10)
        response.raise_for_status()
        data = response.json()['data'][0]
        value = int(data['value'])
        classification = data['value_classification']
        
        emoji = "😱"
        if "Greed" in classification: emoji = "🤑"
        if "Neutral" in classification: emoji = "😐"
        
        meter = "[" + "=" * (value // 10) + " " * (10 - value // 10) + "]"

        return (f"😨😊 **Crypto Fear & Greed Index** 😊😨\n\n"
                f"Current Value: `{value}` - *{classification}*\n"
                f"{meter}\n\n"
                "0-24: Extreme Fear\n25-44: Fear\n45-54: Neutral\n"
                "55-74: Greed\n75-100: Extreme Greed")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Fear & Greed Index: {e}")
        return "Could not retrieve the Fear & Greed Index."

def get_market_overview():
    """Get overall cryptocurrency market data."""
    try:
        response = requests.get(f"{COINGECKO_API}/global", timeout=10)
        response.raise_for_status()
        data = response.json().get("data", {})
        change_icon = "📈" if data.get("market_cap_change_percentage_24h_usd", 0) >= 0 else "📉"
        
        return (f"🌐 *Cryptocurrency Market Overview* 🌐\n\n"
                f"Total Market Cap: `${data.get('total_market_cap', {}).get('usd', 0):,.0f}`\n"
                f"24h Volume: `${data.get('total_volume', {}).get('usd', 0):,.0f}`\n"
                f"24h Change: `{change_icon} {data.get('market_cap_change_percentage_24h_usd', 0):.2f}%`\n"
                f"Bitcoin Dominance: `{data.get('market_cap_percentage', {}).get('btc', 0):.1f}%`\n"
                f"Active Cryptos: `{data.get('active_cryptocurrencies', 0):,}`")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting market overview: {e}")
        return "Could not retrieve market data."

def convert_currency(amount, from_symbol, to_symbol):
    """Convert between cryptocurrencies or to fiat."""
    from_id = get_coin_id_from_symbol(from_symbol)
    to_id = get_coin_id_from_symbol(to_symbol)

    if not from_id or not to_id:
        return None

    try:
        response = requests.get(f"{COINGECKO_API}/simple/price?ids={from_id},{to_id}&vs_currencies=usd", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        from_usd = data.get(from_id, {}).get("usd")
        to_usd = data.get(to_id, {}).get("usd")

        if from_usd is None or to_usd is None:
            return None
        
        rate = from_usd / to_usd
        return float(amount) * rate
    except Exception as e:
        logger.error(f"Conversion error: {e}")
        return None

# --- Telegram Command Handlers ---

async def start_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (f"👋 *Welcome to Crypto Guru!* 👋\n"
               f"Your personal cryptocurrency market assistant\n\n"
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
                 "/feargreed - Fear & Greed Index\n"
                 "/market - Market overview\n"
                 "/convert `<amount> <from> to <to>`\n"
                 "/learn - Crypto education resources\n"
                 "/disclaimer - Show risk warning")
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def trending_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    message = get_cached_data("trending", get_trending_coins)
    await update.message.reply_text(message, parse_mode='Markdown')

async def top_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    message = get_cached_data("top_coins", get_top_coins)
    await update.message.reply_text(message, parse_mode='Markdown')

async def news_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    message = get_cached_data("news", get_crypto_news)
    await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)

async def price_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ℹ️ Please specify a coin. Example: `/price btc`")
        return
    coin_symbol = context.args[0].lower()
    message = get_coin_price(coin_symbol)
    await update.message.reply_text(f"{message}\n\n{DISCLAIMER}", parse_mode='Markdown')

async def price7d_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ℹ️ Please specify a coin. Example: `/price7d btc`")
        return
    coin_symbol = context.args[0].lower()
    historical_data = get_historical_data(coin_symbol, days=7)
    
    if not historical_data:
        await update.message.reply_text(f"❌ Couldn't get historical data for {coin_symbol}.")
        return
        
    chart_buf = generate_price_chart(historical_data)
    await update.message.reply_photo(photo=chart_buf, caption=f"7-day price chart for {coin_symbol.upper()}", parse_mode='Markdown')

async def feargreed_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    message = get_cached_data("fear_greed", get_fear_and_greed_index)
    await update.message.reply_text(f"{message}\n\n{DISCLAIMER}", parse_mode='Markdown')
    
async def market_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    message = get_cached_data("market_overview", get_market_overview)
    await update.message.reply_text(f"{message}\n\n{DISCLAIMER}", parse_mode='Markdown')

async def convert_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 4 or context.args[2].lower() != 'to':
        await update.message.reply_text("ℹ️ Usage: `/convert <amount> <from> to <to>`\nExample: `/convert 1 btc to eth`")
        return
    
    try:
        amount, from_currency, to_currency = float(context.args[0]), context.args[1], context.args[3]
        result = convert_currency(amount, from_currency, to_currency)
        
        if result is None:
            await update.message.reply_text("❌ Couldn't perform conversion. Check your currencies.")
            return
            
        message = (f"💱 *Currency Conversion*\n\n"
                   f"`{amount:,.4f} {from_currency.upper()} = {result:,.4f} {to_currency.upper()}`")
        await update.message.reply_text(f"{message}\n\n{DISCLAIMER}", parse_mode='Markdown')
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Invalid format. Please use numbers for the amount.")

async def learn_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    resources = ("📚 *Crypto Education Resources*\n\n"
                 "• [Bitcoin Whitepaper](https://bitcoin.org/bitcoin.pdf)\n"
                 "• [Ethereum Whitepaper](https://ethereum.org/en/whitepaper/)\n"
                 "• [Binance Academy](https://academy.binance.com/)\n"
                 "• [CoinGecko Learn](https://www.coingecko.com/learn)\n"
                 "• [Crypto Security Guide](https://www.coinbase.com/learn/crypto-basics/crypto-security)")
    await update.message.reply_text(f"{resources}\n\n{DISCLAIMER}", parse_mode='Markdown', disable_web_page_preview=True)

async def disclaimer_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(DISCLAIMER, parse_mode='Markdown')

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    try:
        if update is None:
            logger.error(f"Error: {context.error}")
        else:
            logger.error(f"Update {update} caused error {context.error}")
    except Exception as e:
        logger.error(f"Error in error_handler: {e}")

def main() -> None:
    """Start the bot."""
    # Configure application with better timeout settings
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).read_timeout(30).write_timeout(30).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("trending", trending_command))
    application.add_handler(CommandHandler("top", top_command))
    application.add_handler(CommandHandler("news", news_command))
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("price7d", price7d_command))
    application.add_handler(CommandHandler("feargreed", feargreed_command))
    application.add_handler(CommandHandler("market", market_command))
    application.add_handler(CommandHandler("convert", convert_command))
    application.add_handler(CommandHandler("learn", learn_command))
    application.add_handler(CommandHandler("disclaimer", disclaimer_command))
    
    # Add error handler
    application.add_error_handler(error_handler)

    # Start polling
    logger.info("Crypto Guru bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
