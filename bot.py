# Keep alive for hosting platforms like Replit
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

# --- EXPANDED: Public, Keyless API Endpoints ---
COINGECKO_API = "https://api.coingecko.com/api/v3"
ALTERNATIVE_API = "https://api.alternative.me"
BINANCE_API = "https://api.binance.com/api/v3"
KUCOIN_API = "https://api.kucoin.com/api/v1"
BYBIT_API = "https://api.bybit.com/v2/public"
GATEIO_API = "https://api.gateio.ws/api/v4"
MEXC_API = "https://api.mexc.com/api/v3"
BITFINEX_API = "https://api-pub.bitfinex.com/v2"
OKX_API = "https://www.okx.com/api/v5/market"
COINEX_API = "https://api.coinex.com/v2/market"
BITSTAMP_API = "https://www.bitstamp.net/api/v2"


NEWS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundsfeeds/rss/",
    "https://decrypt.co/feed",
    "https://cryptopanic.com/news/public/?feed=rss"
]

# --- Rate Limiting & Caching ---
CACHE = {}
CACHE_EXPIRY = 180  # 3 minutes
API_SEMAPHORE = asyncio.Semaphore(10) # Increased semaphore for more concurrent checks
MAX_RETRIES = 2

# --- Common Coin Aliases ---
COIN_ALIASES = {
    'ton': 'the-open-network', 'bnb': 'binancecoin', 'shib': 'shiba-inu',
    'w': 'wormhole', 'usdt': 'tether'
}

# --- Global HTTP Client ---
api_client = httpx.AsyncClient(timeout=15)

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
    """A robust, rate-limited, and retrying API request handler."""
    async with API_SEMAPHORE:
        for attempt in range(MAX_RETRIES):
            try:
                response = await api_client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error(f"HTTP error for {e.request.url}: {e}")
                    return None
            except httpx.RequestError as e:
                logger.error(f"Request error for {e.request.url}: {e}")
                return None
    logger.error(f"API request failed for {url} after {MAX_RETRIES} retries.")
    return None

async def get_cached_data(key, func, *args, **kwargs):
    now = time.time()
    if key in CACHE and now - CACHE[key]['timestamp'] < CACHE_EXPIRY:
        logger.info(f"Serving from cache for key: {key}")
        return CACHE[key]['data']
    data = await func(*args, **kwargs)
    if data:
        CACHE[key] = {'data': data, 'timestamp': now}
    return data

async def _fetch_coins_list():
    return await make_api_request(f"{COINGECKO_API}/coins/list")

async def get_coin_id_from_symbol(symbol: str):
    query = symbol.lower()
    if query in COIN_ALIASES: return COIN_ALIASES[query]
    coin_list = await get_cached_data("coins_list", _fetch_coins_list)
    if not coin_list: return None
    for coin in coin_list:
        if coin['id'] == query or coin['symbol'] == query or coin['name'].lower() == query:
            return coin['id']
    return None

# --- NEW: Expanded Fallback Price Fetching Functions ---

def _format_fallback_message(source: str, symbol: str, price: float, change: float, volume: float):
    """Standardizes the output message for all fallback sources."""
    change_emoji = "📈" if change >= 0 else "📉"
    return (f"**{symbol.upper()}/USDT Price (via {source})**\n\n"
            f"💰 **Price:** ${price:,.4f}\n"
            f"{change_emoji} **24h Change:** {change:.2f}%\n"
            f"📊 **24h Volume:** ${volume:,.2f}\n"
            f"ℹ️ _Market cap data not available on this source._")

async def _fetch_price_from_binance(symbol: str):
    logger.info(f"Trying fallback (Binance) for {symbol.upper()}")
    params = {'symbol': f'{symbol.upper()}USDT'}
    data = await make_api_request(f"{BINANCE_API}/ticker/24hr", params=params)
    if not data: return None
    try:
        return {"price": float(data['lastPrice']), "change": float(data['priceChangePercent']), "volume": float(data['quoteVolume']), "source": "Binance"}
    except (TypeError, KeyError): return None

async def _fetch_price_from_kucoin(symbol: str):
    logger.info(f"Trying fallback (KuCoin) for {symbol.upper()}")
    params = {'symbol': f'{symbol.upper()}-USDT'}
    data = await make_api_request(f"{KUCOIN_API}/market/stats", params=params)
    if not data or not data.get('data'): return None
    try:
        d = data['data']
        return {"price": float(d['last']), "change": float(d['changeRate']) * 100, "volume": float(d['volValue']), "source": "KuCoin"}
    except (TypeError, KeyError): return None

async def _fetch_price_from_bybit(symbol: str):
    logger.info(f"Trying fallback (Bybit) for {symbol.upper()}")
    params = {'symbol': f'{symbol.upper()}USDT'}
    data = await make_api_request(f"{BYBIT_API}/tickers", params=params)
    if not data or not data.get('result'): return None
    try:
        d = data['result'][0]
        return {"price": float(d['last_price']), "change": float(d['price_24h_pcnt']) * 100, "volume": float(d['turnover_24h']), "source": "Bybit"}
    except (TypeError, KeyError, IndexError): return None

async def _fetch_price_from_gateio(symbol: str):
    logger.info(f"Trying fallback (Gate.io) for {symbol.upper()}")
    params = {'currency_pair': f'{symbol.upper()}_USDT'}
    data = await make_api_request(f"{GATEIO_API}/spot/tickers", params=params)
    if not data: return None
    try:
        d = data[0]
        return {"price": float(d['last']), "change": float(d['change_percentage']), "volume": float(d['quote_volume']), "source": "Gate.io"}
    except (TypeError, KeyError, IndexError): return None

async def _fetch_price_from_mexc(symbol: str):
    logger.info(f"Trying fallback (MEXC) for {symbol.upper()}")
    params = {'symbol': f'{symbol.upper()}USDT'}
    data = await make_api_request(f"{MEXC_API}/ticker/24hr", params=params)
    if not data: return None
    try:
        return {"price": float(data['lastPrice']), "change": float(data['priceChangePercent']), "volume": float(data['quoteVolume']), "source": "MEXC"}
    except (TypeError, KeyError): return None

async def _fetch_price_from_bitfinex(symbol: str):
    logger.info(f"Trying fallback (Bitfinex) for {symbol.upper()}")
    data = await make_api_request(f"{BITFINEX_API}/ticker/t{symbol.upper()}USD")
    if not data: return None
    try:
        return {"price": float(data[6]), "change": float(data[5]) * 100, "volume": float(data[7]), "source": "Bitfinex"}
    except (TypeError, KeyError, IndexError): return None

async def _fetch_price_from_okx(symbol: str):
    logger.info(f"Trying fallback (OKX) for {symbol.upper()}")
    params = {'instId': f'{symbol.upper()}-USDT'}
    data = await make_api_request(f"{OKX_API}/ticker", params=params)
    if not data or not data.get('data'): return None
    try:
        d = data['data'][0]
        return {"price": float(d['last']), "change": float(d['chg24h']) * 100, "volume": float(d['vol24h']), "source": "OKX"}
    except (TypeError, KeyError, IndexError): return None

async def _fetch_price_from_coinex(symbol: str):
    logger.info(f"Trying fallback (CoinEx) for {symbol.upper()}")
    params = {'market': f'{symbol.upper()}USDT'}
    data = await make_api_request(f"{COINEX_API}/ticker", params=params)
    if not data or not data.get('data'): return None
    try:
        d = data['data']['ticker']
        return {"price": float(d['last']), "change": float(d['percent']), "volume": float(d['value']), "source": "CoinEx"}
    except (TypeError, KeyError): return None

async def _fetch_price_from_bitstamp(symbol: str):
    logger.info(f"Trying fallback (Bitstamp) for {symbol.upper()}")
    data = await make_api_request(f"{BITSTAMP_API}/ticker/{symbol.lower()}usd/")
    if not data: return None
    try:
        return {"price": float(data['last']), "change": float(data['percent_change_24']), "volume": float(data['volume']), "source": "Bitstamp"}
    except (TypeError, KeyError): return None

# --- MODIFIED: Main Feature Function with 10-Tier Fallback System ---

async def _get_price_data_from_all_sources(symbol: str):
    """Internal function to fetch raw price data from the entire fallback chain."""
    # Attempt 1: CoinGecko (Primary)
    coin_id = await get_coin_id_from_symbol(symbol)
    if coin_id:
        params = {"ids": coin_id, "vs_currencies": "usd", "include_market_cap": "true",
                  "include_24hr_vol": "true", "include_24hr_change": "true"}
        data = await make_api_request(f"{COINGECKO_API}/simple/price", params=params)
        if data and coin_id in data:
            d = data[coin_id]
            return {"price": d.get('usd', 0), "change": d.get('usd_24h_change', 0), 
                    "volume": d.get('usd_24h_vol', 0), "market_cap": d.get('usd_market_cap', 0), 
                    "source": "CoinGecko", "coin_id": coin_id}

    # --- Fallback Chain ---
    fallback_functions = [
        _fetch_price_from_binance, _fetch_price_from_kucoin, _fetch_price_from_bybit,
        _fetch_price_from_gateio, _fetch_price_from_mexc, _fetch_price_from_bitfinex,
        _fetch_price_from_okx, _fetch_price_from_coinex, _fetch_price_from_bitstamp
    ]
    for func in fallback_functions:
        result = await func(symbol)
        if result:
            return result
    return None

async def get_coin_price(symbol: str):
    """Formats the raw price data into a user-facing message."""
    data = await _get_price_data_from_all_sources(symbol)
    if not data:
        return f"❌ Could not find price data for '{symbol.upper()}' from 10 different public sources."

    if data['source'] == 'CoinGecko':
        change = data.get('change', 0) or 0
        change_emoji = "📈" if change >= 0 else "📉"
        return (f"**{symbol.upper()} ({data['coin_id'].replace('-', ' ').title()}) Price (via CoinGecko)**\n\n"
                f"💰 **Price:** ${data.get('price', 0):,.4f}\n"
                f"{change_emoji} **24h Change:** {change:.2f}%\n"
                f"📊 **24h Volume:** ${data.get('volume', 0):,.2f}\n"
                f"🏦 **Market Cap:** ${data.get('market_cap', 0):,.2f}\n")
    else:
        return _format_fallback_message(data['source'], symbol, data['price'], data['change'], data['volume'])

# --- Other Feature Functions (MODIFIED with fallbacks where possible) ---

async def _fetch_historical_from_binance(symbol: str, days: int):
    """Fallback for historical data using Binance k-lines."""
    logger.info(f"Trying fallback (Binance) for {symbol.upper()} historical data.")
    params = {'symbol': f'{symbol.upper()}USDT', 'interval': '1d', 'limit': days}
    data = await make_api_request(f"{BINANCE_API}/klines", params=params)
    if not data: return None
    try:
        timestamps = [pd.to_datetime(p[0], unit='ms') for p in data]
        values = [float(p[4]) for p in data] # Use closing price
        return {"timestamps": timestamps, "prices": values, "coin": symbol.upper(), "source": "Binance"}
    except (TypeError, KeyError, IndexError): return None

async def get_historical_data(symbol: str, days=7):
    """Get historical data, trying CoinGecko then falling back to Binance."""
    coin_id = await get_coin_id_from_symbol(symbol)
    if coin_id:
        params = {"vs_currency": "usd", "days": str(days)}
        data = await make_api_request(f"{COINGECKO_API}/coins/{coin_id}/market_chart", params=params)
        if data and "prices" in data:
            prices = data["prices"]
            timestamps = [pd.to_datetime(p[0], unit='ms') for p in prices]
            values = [p[1] for p in prices]
            return {"timestamps": timestamps, "prices": values, "coin": symbol.upper(), "source": "CoinGecko"}

    binance_data = await _fetch_historical_from_binance(symbol, days)
    if binance_data: return binance_data
    return None

def generate_price_chart(historical_data):
    source = historical_data.get("source", "Unknown Source")
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5), facecolor='#1e1e1e')
    ax.set_facecolor('#1e1e1e')
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('grey'); ax.spines['left'].set_color('grey')
    ax.plot(historical_data["timestamps"], historical_data["prices"], color='#00aaff', linewidth=2)
    ax.set_title(f"{historical_data['coin']} 7-Day Price Chart (via {source})", color='white', fontsize=16)
    ax.set_xlabel("Date", color='grey'); ax.set_ylabel("Price (USD)", color='grey')
    ax.grid(True, linestyle='--', alpha=0.2)
    ax.tick_params(axis='x', colors='grey'); ax.tick_params(axis='y', colors='grey')
    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), dpi=100)
    buf.seek(0)
    plt.close(fig)
    return buf

async def get_trending_coins():
    data = await make_api_request(f"{COINGECKO_API}/search/trending")
    if not data or 'coins' not in data: return "Could not retrieve trending coins. This feature relies on CoinGecko and may be temporarily unavailable."
    message = "🔥 **Top 10 Trending Coins** 🔥\n\n"
    for i, coin in enumerate(data['coins'][:10]):
        item = coin['item']
        message += (f"{i+1}. **{item['name']} ({item['symbol'].upper()})**\n"
                    f"   - Rank: {item['market_cap_rank']}\n"
                    f"   - Price (BTC): {item.get('price_btc', 0):.8f}\n\n")
    return message

async def _fetch_top_coins_from_binance(limit=20):
    """Fallback for top coins, sorted by 24h volume from Binance."""
    logger.info("Trying fallback (Binance) for top coins list.")
    data = await make_api_request(f"{BINANCE_API}/ticker/24hr")
    if not data: return None
    
    usdt_pairs = [t for t in data if t['symbol'].endswith('USDT')]
    usdt_pairs.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
    
    message = "🏆 *Top 20 Cryptocurrencies by 24h Volume (via Binance)* 🏆\n\n"
    for i, coin in enumerate(usdt_pairs[:limit]):
        change_icon = "📈" if float(coin.get("priceChangePercent", 0)) >= 0 else "📉"
        symbol = coin['symbol'].replace('USDT', '')
        message += (f"{i+1}. **{symbol}**\n"
                    f"   - Price: ${float(coin.get('lastPrice', 0)):,.4f}\n"
                    f"   - 24h Change: {change_icon} {float(coin.get('priceChangePercent', 0)):.2f}%\n"
                    f"   - 24h Volume: ${float(coin.get('quoteVolume', 0)):,}\n\n")
    return message

async def get_top_coins(limit=20):
    """Get top coins by market cap from CoinGecko, with a volume-based fallback from Binance."""
    params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": limit, "page": 1}
    coins = await make_api_request(f"{COINGECKO_API}/coins/markets", params=params)
    if coins:
        message = "🏆 *Top 20 Cryptocurrencies by Market Cap (via CoinGecko)* 🏆\n\n"
        for coin in coins:
            change_icon = "📈" if coin.get("price_change_percentage_24h", 0) >= 0 else "📉"
            message += (f"{coin.get('market_cap_rank', 'N/A')}. **{coin.get('name', 'N/A')} ({coin.get('symbol', '').upper()})**\n"
                        f"   - Price: ${coin.get('current_price', 0):,.2f}\n"
                        f"   - 24h Change: {change_icon} {coin.get('price_change_percentage_24h', 0):.2f}%\n"
                        f"   - Market Cap: ${coin.get('market_cap', 0):,}\n\n")
        return message

    binance_fallback = await _fetch_top_coins_from_binance(limit)
    if binance_fallback: return binance_fallback

    return "Could not retrieve top coins from any available source."

def get_crypto_news():
    all_entries = []
    for feed_url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                publish_time = entry.get('published_parsed', datetime.now().timetuple())
                all_entries.append({'title': entry.title, 'link': entry.link, 'source': feed.feed.title, 'published': datetime.fromtimestamp(time.mktime(publish_time))})
        except Exception as e:
            logger.error(f"Could not parse feed {feed_url}: {e}")
    if not all_entries: return "Could not retrieve crypto news."
    all_entries.sort(key=itemgetter('published'), reverse=True)
    message = "📰 **Latest Crypto News** 📰\n\n"
    for entry in all_entries[:10]:
        message += f"• [{entry['title']}]({entry['link']}) ({entry['source']})\n"
    return message

async def get_fear_and_greed_index():
    data = await make_api_request(f"{ALTERNATIVE_API}/fng/")
    if not data or 'data' not in data: return "Could not retrieve the Fear & Greed Index."
    value = int(data['data'][0]['value'])
    classification = data['data'][0]['value_classification']
    emoji = {"Extreme Fear": "😱", "Fear": "😨", "Neutral": "😐", "Greed": "😊", "Extreme Greed": "🤑"}.get(classification, "🤔")
    meter = "[" + "🟩" * (value // 10) + "⬜️" * (10 - value // 10) + "]"
    return (f"{emoji} **Crypto Fear & Greed Index**\n\n"
            f"Current Value: `{value}` - *{classification}*\n{meter}\n\n"
            "0-24: Extreme Fear\n25-44: Fear\n45-54: Neutral\n"
            "55-74: Greed\n75-100: Extreme Greed")

async def get_market_overview():
    data = await make_api_request(f"{COINGECKO_API}/global")
    if not data or 'data' not in data: return "Could not retrieve market data. This feature relies on CoinGecko and may be temporarily unavailable."
    d = data['data']
    change_icon = "📈" if d.get("market_cap_change_percentage_24h_usd", 0) >= 0 else "📉"
    return (f"🌐 *Cryptocurrency Market Overview* 🌐\n\n"
            f"Total Market Cap: `${d.get('total_market_cap', {}).get('usd', 0):,.0f}`\n"
            f"24h Volume: `${d.get('total_volume', {}).get('usd', 0):,.0f}`\n"
            f"24h Change: {change_icon} {d.get('market_cap_change_percentage_24h_usd', 0):.2f}%\n"
            f"Bitcoin Dominance: `{d.get('market_cap_percentage', {}).get('btc', 0):.1f}%`\n"
            f"Active Cryptos: `{d.get('active_cryptocurrencies', 0):,}`")

async def convert_currency(amount, from_symbol, to_symbol):
    """Performs currency conversion, now with a highly resilient price fetching fallback."""
    # Efficient primary method
    from_id, to_id = await asyncio.gather(get_coin_id_from_symbol(from_symbol), get_coin_id_from_symbol(to_symbol))
    if from_id and to_id:
        params = {"ids": f"{from_id},{to_id}", "vs_currencies": "usd"}
        data = await make_api_request(f"{COINGECKO_API}/simple/price", params=params)
        if data and from_id in data and to_id in data:
            from_usd = data[from_id].get("usd"); to_usd = data[to_id].get("usd")
            if from_usd is not None and to_usd is not None and to_usd != 0:
                return float(amount) * (from_usd / to_usd)

    # Resilient fallback method
    logger.info("Primary conversion failed, using resilient price fallback.")
    from_data, to_data = await asyncio.gather(
        _get_price_data_from_all_sources(from_symbol),
        _get_price_data_from_all_sources(to_symbol)
    )
    if from_data and to_data and from_data.get('price') and to_data.get('price'):
        from_usd = from_data['price']; to_usd = to_data['price']
        if to_usd != 0:
            return float(amount) * (from_usd / to_usd)

    return None

# --- Telegram Command Handlers ---

async def start_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (f"👋 *Welcome to Crypto Guru!* 👋\n"
               f"Your personal cryptocurrency market assistant.\n\n{DISCLAIMER}")
    await update.message.reply_text(welcome, parse_mode='Markdown')
    await help_command(update, context)

async def help_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    commands_list = await context.bot.get_my_commands()
    help_text = "*Available Commands:*\n" + "\n".join(f"/{cmd.command} - {cmd.description}" for cmd in commands_list)
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
    coin_symbol = context.args[0].lower()
    message = await get_cached_data(f"price_{coin_symbol}", get_coin_price, coin_symbol)
    await update.message.reply_text(message, parse_mode='Markdown')

async def price7d_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ℹ️ Please specify a coin. Example: `/price7d btc`")
        return
    coin_symbol = context.args[0].lower()
    await update.message.reply_text(f"⏳ Generating chart for {coin_symbol.upper()}...")
    historical_data = await get_cached_data(f"history7d_{coin_symbol}", get_historical_data, coin_symbol, days=7)
    if not historical_data:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Couldn't get historical data for {coin_symbol.upper()} from any available source.")
        return
    chart_buf = await asyncio.to_thread(generate_price_chart, historical_data)
    await update.message.reply_photo(photo=chart_buf, parse_mode='Markdown')

async def feargreed_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    message = await get_cached_data("fear_greed", get_fear_and_greed_index)
    await update.message.reply_text(message, parse_mode='Markdown')

async def market_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    message = await get_cached_data("market_overview", get_market_overview)
    await update.message.reply_text(message, parse_mode='Markdown')

async def convert_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 4 or context.args[2].lower() != 'to':
        await update.message.reply_text("ℹ️ Usage: `/convert <amount> <from> to <to>`")
        return
    try:
        amount, from_currency, to_currency = float(context.args[0]), context.args[1], context.args[3]
        result = await convert_currency(amount, from_currency, to_currency)
        if result is None:
            await update.message.reply_text("❌ Couldn't perform conversion. Check currencies or try again.")
            return
        message = (f"💱 *Currency Conversion*\n\n"
                   f"`{amount:,.4f} {from_currency.upper()} = {result:,.4f} {to_currency.upper()}`")
        await update.message.reply_text(message, parse_mode='Markdown')
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Invalid format.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

async def post_init(application: Application):
    await application.bot.set_my_commands([
        ('start', 'Start the bot and see help'),
        ('trending', 'See top 10 trending coins (CoinGecko)'),
        ('top', 'See top coins (with fallback)'),
        ('price', 'Get coin price (10+ backup sources)'),
        ('price7d', 'Get 7-day price chart (with fallback)'),
        ('news', 'Get latest crypto news'),
        ('feargreed', 'Check the Fear & Greed Index'),
        ('market', 'Get market overview (CoinGecko)'),
        ('convert', 'Convert currencies (resilient)'),
        ('help', 'Show this help message'),
    ])
    logger.info("Custom bot commands have been set.")

async def on_shutdown(application: Application):
    await api_client.aclose()
    logger.info("HTTP client closed.")

def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is not set as an environment variable.")
        return

    builder = Application.builder().token(TELEGRAM_BOT_TOKEN)
    builder.post_init(post_init)
    builder.post_shutdown(on_shutdown)
    application = builder.build()

    handlers = [
        CommandHandler("start", start_command), CommandHandler("help", help_command),
        CommandHandler("trending", trending_command), CommandHandler("top", top_command),
        CommandHandler("news", news_command), CommandHandler("price", price_command),
        CommandHandler("price7d", price7d_command), CommandHandler("feargreed", feargreed_command),
        CommandHandler("market", market_command), CommandHandler("convert", convert_command)
    ]
    application.add_handlers(handlers)
    application.add_error_handler(error_handler)

    logger.info("Crypto Guru bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    keep_alive_thread = threading.Thread(target=keep_alive)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()
    main()
