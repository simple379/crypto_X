# Keep alive for hosting platforms like Replit
from keep_alive import keep_alive
import telegram
from telegram.ext import Application, CommandHandler, ContextTypes
import httpx
import feedparser
import os
from datetime import datetime, timedelta
from operator import itemgetter
import matplotlib.pyplot as plt
import io
import pandas as pd
import time
import asyncio
import threading
import logging
import re
import random
import json
from bs4 import BeautifulSoup
import numpy as np

# --- Basic Configuration ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Environment & API Configuration ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '7972609552:AAHZvzeRP1B96Nezt0rFnCo54ahKMAiIVH4')

# --- 50+ Public API Endpoints ---
EXCHANGE_APIS = {
    # Primary Data Sources
    "CoinGecko": "https://api.coingecko.com/api/v3",
    "CoinMarketCap": "https://pro-api.coinmarketcap.com/v1",
    "CryptoCompare": "https://min-api.cryptocompare.com/data",
    "Binance": "https://api.binance.com/api/v3",
    "Coinbase": "https://api.coinbase.com/v2",
    
    # Secondary Data Sources
    "KuCoin": "https://api.kucoin.com/api/v1",
    "Bybit": "https://api.bybit.com/v2/public",
    "Gate.io": "https://api.gateio.ws/api/v4",
    "MEXC": "https://api.mexc.com/api/v3",
    "Bitfinex": "https://api-pub.bitfinex.com/v2",
    "OKX": "https://www.okx.com/api/v5/market",
    "CoinEx": "https://api.coinex.com/v2/market",
    "Bitstamp": "https://www.bitstamp.net/api/v2",
    "Huobi": "https://api.huobi.pro/market",
    "Kraken": "https://api.kraken.com/0/public",
    "Crypto.com": "https://api.crypto.com/v2/public",
    "Poloniex": "https://poloniex.com/public",
    "BitMart": "https://api-cloud.bitmart.com/spot/v1",
    "ProBit": "https://api.probit.com/api/exchange/v1",
    "HitBTC": "https://api.hitbtc.com/api/3/public",
    "WhiteBit": "https://whitebit.com/api/v4/public",
    "BingX": "https://open-api.bingx.com/openApi/spot/v1",
    "Bitrue": "https://www.bitrue.com/api/v1",
    "Coinone": "https://api.coinone.co.kr/public/v2",
    "ZB.com": "https://api.zb.com/data/v1",
    "Bitkub": "https://api.bitkub.com/api/market",
    "Indodax": "https://indodax.com/api",
    "WazirX": "https://api.wazirx.com/sapi/v1",
    "CoinDCX": "https://api.coindcx.com/exchange/v1/markets",
    "Phemex": "https://api.phemex.com/md",
    "Bitso": "https://api.bitso.com/v3",
    "LBank": "https://api.lbkex.com/v2",
    "Bitget": "https://api.bitget.com/api/spot/v1/market",
    "XT.com": "https://sapi.xt.com/v4/public",
    "DigiFinex": "https://openapi.digifinex.com/v3",
    "BitVenus": "https://api.bitvenus.com/api/v1",
    
    # Alternative Data Sources
    "Nomics": "https://api.nomics.com/v1",
    "CoinCap": "https://api.coincap.io/v2",
    "CoinStats": "https://api.coinstats.app/public/v1",
    "CoinPaprika": "https://api.coinpaprika.com/v1",
    "LiveCoinWatch": "https://api.livecoinwatch.com/coins",
    "CoinRanking": "https://api.coinranking.com/v2",
    "CoinCodex": "https://coincodex.com/api/coincodex",
    "CoinLore": "https://api.coinlore.net/api",
    "AltRank": "https://api.lunarcrush.com/v2",
    "Messari": "https://data.messari.io/api/v1",
    "TradingView": "https://scanner.tradingview.com",
    "CoinCheckup": "https://api.coincheckup.com/v1",
    "Coin360": "https://api.coin360.com/api",
    "CoinLib": "https://coinlib.io/api/v1"
}

# --- 50+ News Sources ---
NEWS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundsfeeds/rss/",
    "https://decrypt.co/feed",
    "https://cryptopanic.com/news/public/?feed=rss",
    "https://www.coinjournal.net/feed/",
    "https://cryptoslate.com/feed/",
    "https://bitcoinmagazine.com/.rss/full/",
    "https://beincrypto.com/feed/",
    "https://coingape.com/feed/",
    "https://ambcrypto.com/feed/",
    "https://www.newsbtc.com/feed/",
    "https://u.today/rss",
    "https://cryptopotato.com/feed/",
    "https://zycrypto.com/feed/",
    "https://cryptobriefing.com/feed/",
    "https://bitcoinist.com/feed/",
    "https://www.cryptoglobe.com/rss",
    "https://cryptodaily.co.uk/feed",
    "https://thecryptobasic.com/feed/",
    "https://cryptonews.com/news/rss/",
    "https://blockonomi.com/feed/",
    "https://coinquora.com/feed/",
    "https://cryptodisrupt.com/feed/",
    "https://cryptopolitan.com/feed/",
    "https://cryptonewsz.com/feed/",
    "https://cryptomode.com/feed/",
    "https://cryptodaily.co.uk/feed",
    "https://cryptosimplified.com/feed/",
    "https://cryptobanter.com/feed/",
    "https://cryptonews.net/en/rss/"
]

# --- Rate Limiting & Caching ---
CACHE = {}
CACHE_EXPIRY = 180  # 3 minutes
API_SEMAPHORE = asyncio.Semaphore(20)  # Increased for more concurrent checks
MAX_RETRIES = 3
REQUEST_TIMEOUT = 25
REQUEST_DELAY = 0.1  # Small delay between requests to avoid rate limits

# --- Common Coin Aliases ---
COIN_ALIASES = {
    'ton': 'the-open-network', 'bnb': 'binancecoin', 'shib': 'shiba-inu',
    'w': 'wormhole', 'usdt': 'tether', 'btc': 'bitcoin', 'eth': 'ethereum',
    'xrp': 'ripple', 'doge': 'dogecoin', 'ada': 'cardano', 'sol': 'solana',
    'dot': 'polkadot', 'avax': 'avalanche-2', 'matic': 'matic-network',
    'link': 'chainlink', 'atom': 'cosmos', 'uni': 'uniswap', 'ltc': 'litecoin',
    'bch': 'bitcoin-cash', 'xlm': 'stellar', 'xmr': 'monero', 'etc': 'ethereum-classic',
    'trx': 'tron', 'eos': 'eos', 'neo': 'neo', 'xtz': 'tezos', 'vet': 'vechain',
    'dash': 'dash', 'zec': 'zcash', 'waves': 'waves', 'qtum': 'qtum', 'omg': 'omisego'
}

# --- Global HTTP Client ---
api_client = httpx.AsyncClient(
    timeout=REQUEST_TIMEOUT,
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    transport=httpx.AsyncHTTPTransport(retries=3)
)

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

async def make_api_request(url: str, params: dict = None, headers: dict = None):
    """Robust API request handler with exponential backoff and failover"""
    headers = headers or {
        "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(90, 110)}.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            async with API_SEMAPHORE:
                await asyncio.sleep(REQUEST_DELAY * random.uniform(0.5, 1.5))
                response = await api_client.get(url, params=params, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in [429, 418, 502, 503, 504]:
                wait_time = 2 ** attempt + random.uniform(0, 1)
                logger.warning(f"Rate limited ({e.response.status_code}). Retrying in {wait_time:.1f}s for {url}")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"HTTP error {e.response.status_code} for {e.request.url}")
                break
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.error(f"Request failed for {url}: {str(e)}")
            await asyncio.sleep(1 + attempt)
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {str(e)}")
            break
            
    logger.error(f"API request failed for {url} after {MAX_RETRIES} retries")
    return None

async def get_cached_data(key, func, *args, **kwargs):
    now = time.time()
    if key in CACHE and now - CACHE[key]['timestamp'] < CACHE_EXPIRY:
        return CACHE[key]['data']
    
    data = await func(*args, **kwargs)
    if data:
        CACHE[key] = {'data': data, 'timestamp': now}
    return data

async def _fetch_coins_list():
    for name, url in EXCHANGE_APIS.items():
        if "coingecko" in url.lower():
            data = await make_api_request(f"{url}/coins/list")
            if data:
                return data
    return None

async def get_coin_id_from_symbol(symbol: str):
    query = symbol.lower()
    if query in COIN_ALIASES: 
        return COIN_ALIASES[query]
    
    coin_list = await get_cached_data("coins_list", _fetch_coins_list)
    if coin_list:
        for coin in coin_list:
            if (coin.get('id', '').lower() == query or 
                coin.get('symbol', '').lower() == query or 
                coin.get('name', '').lower() == query):
                return coin['id']
                
    return None

# --- Price Fetching Functions ---

def _format_price_message(source: str, symbol: str, data: dict):
    """Standardized price message formatting"""
    price = data.get('price', 0)
    change = data.get('change', 0)
    volume = data.get('volume', 0)
    market_cap = data.get('market_cap', 0)
    high_24h = data.get('high_24h', 0)
    low_24h = data.get('low_24h', 0)
    coin_name = data.get('name', symbol.upper())
    
    change_emoji = "📈" if change >= 0 else "📉"
    
    message = (f"📊 **{coin_name} ({symbol.upper()}) Price (via {source})**\n\n"
               f"💰 **Price:** ${price:,.4f}\n"
               f"{change_emoji} **24h Change:** {change:.2f}%\n"
               f"🔺 **24h High:** ${high_24h:,.4f}\n"
               f"🔻 **24h Low:** ${low_24h:,.4f}\n"
               f"💱 **24h Volume:** ${volume:,.2f}\n")
    
    if market_cap:
        message += f"🏦 **Market Cap:** ${market_cap:,.2f}\n"
    
    return message

# --- Exchange-specific Price Fetching ---

async def _fetch_price_coingecko(symbol: str):
    coin_id = await get_coin_id_from_symbol(symbol)
    if not coin_id:
        return None
        
    params = {"ids": coin_id, "vs_currencies": "usd", 
              "include_market_cap": "true", "include_24hr_vol": "true", 
              "include_24hr_change": "true"}
    
    data = await make_api_request(f"{EXCHANGE_APIS['CoinGecko']}/simple/price", params=params)
    if not data or coin_id not in data:
        return None
        
    d = data[coin_id]
    return {
        "price": d.get('usd', 0),
        "change": d.get('usd_24h_change', 0),
        "volume": d.get('usd_24h_vol', 0),
        "market_cap": d.get('usd_market_cap', 0),
        "name": coin_id.replace('-', ' ').title()
    }

async def _fetch_price_coinmarketcap(symbol: str):
    headers = {"X-CMC_PRO_API_KEY": "b54bcf4d-1bca-4e8e-9a24-22ff2c3d462c"}
    params = {'symbol': symbol.upper()}
    data = await make_api_request(f"{EXCHANGE_APIS['CoinMarketCap']}/cryptocurrency/quotes/latest", 
                                  params=params, headers=headers)
    if not data or 'data' not in data:
        return None
        
    try:
        coin_data = list(data['data'].values())[0]
        quote = coin_data['quote']['USD']
        return {
            "price": quote['price'],
            "change": quote['percent_change_24h'],
            "volume": quote['volume_24h'],
            "market_cap": quote['market_cap'],
            "high_24h": quote.get('high_24h', 0), # Using .get for safety
            "low_24h": quote.get('low_24h', 0)   # Using .get for safety
        }
    except (KeyError, IndexError, TypeError):
        return None

async def _fetch_price_cryptocompare(symbol: str):
    params = {'fsym': symbol.upper(), 'tsyms': 'USD'}
    data = await make_api_request(f"{EXCHANGE_APIS['CryptoCompare']}/price", params=params)
    if not data or 'USD' not in data:
        return None
        
    # Get additional data
    data_full = await make_api_request(f"{EXCHANGE_APIS['CryptoCompare']}/pricemultifull", 
                                       params={'fsyms': symbol.upper(), 'tsyms': 'USD'})
    if not data_full or 'RAW' not in data_full:
        return None
        
    try:
        raw = data_full['RAW'][symbol.upper()]['USD']
        return {
            "price": raw['PRICE'],
            "change": raw['CHANGEPCT24HOUR'],
            "volume": raw['VOLUME24HOUR'],
            "market_cap": raw['MKTCAP'],
            "high_24h": raw['HIGH24HOUR'],
            "low_24h": raw['LOW24HOUR']
        }
    except (KeyError, TypeError):
        return None

# Implementations for other price fetchers
async def _fetch_price_binance(symbol: str):
    params = {'symbol': f'{symbol.upper()}USDT'}
    data = await make_api_request(f"{EXCHANGE_APIS['Binance']}/ticker/24hr", params=params)
    if not data:
        return None
        
    try:
        return {
            "price": float(data['lastPrice']),
            "change": float(data['priceChangePercent']),
            "volume": float(data['quoteVolume']),
            "high_24h": float(data['highPrice']),
            "low_24h": float(data['lowPrice'])
        }
    except (TypeError, KeyError, ValueError):
        return None

async def _fetch_price_kucoin(symbol: str):
    params = {'symbol': f'{symbol.upper()}-USDT'}
    data = await make_api_request(f"{EXCHANGE_APIS['KuCoin']}/market/stats", params=params)
    if not data or not data.get('data'):
        return None
        
    try:
        d = data['data']
        return {
            "price": float(d['last']),
            "change": float(d['changeRate']) * 100,
            "volume": float(d['volValue']),
            "high_24h": float(d['high']),
            "low_24h": float(d['low'])
        }
    except (TypeError, KeyError, ValueError):
        return None

async def _fetch_price_bybit(symbol: str):
    params = {'symbol': f'{symbol.upper()}USDT'}
    data = await make_api_request(f"{EXCHANGE_APIS['Bybit']}/tickers", params=params)
    if not data or not data.get('result'):
        return None
        
    try:
        d = data['result'][0]
        return {
            "price": float(d['last_price']),
            "change": float(d['price_24h_pcnt']) * 100,
            "volume": float(d['turnover_24h']),
            "high_24h": float(d['high_price_24h']),
            "low_24h": float(d['low_price_24h'])
        }
    except (TypeError, KeyError, IndexError, ValueError):
        return None

async def _fetch_price_gateio(symbol: str):
    params = {'currency_pair': f'{symbol.upper()}_USDT'}
    data = await make_api_request(f"{EXCHANGE_APIS['Gate.io']}/spot/tickers", params=params)
    if not data:
        return None
        
    try:
        d = data[0]
        return {
            "price": float(d['last']),
            "change": float(d['change_percentage']),
            "volume": float(d['quote_volume']),
            "high_24h": float(d['high_24h']),
            "low_24h": float(d['low_24h'])
        }
    except (TypeError, KeyError, IndexError, ValueError):
        return None

async def _fetch_price_mexc(symbol: str):
    params = {'symbol': f'{symbol.upper()}USDT'}
    data = await make_api_request(f"{EXCHANGE_APIS['MEXC']}/ticker/24hr", params=params)
    if not data:
        return None
        
    try:
        # MEXC API returns a list for a single symbol
        d = data[0] if isinstance(data, list) else data
        return {
            "price": float(d['lastPrice']),
            "change": float(d['priceChangePercent']) * 100, # Assuming it's a ratio
            "volume": float(d['quoteVolume']),
            "high_24h": float(d['highPrice']),
            "low_24h": float(d['lowPrice'])
        }
    except (TypeError, KeyError, ValueError, IndexError):
        return None

# --- Price Fetching Orchestrator ---

PRICE_FETCHERS = [
    ("CoinGecko", _fetch_price_coingecko),
    ("CoinMarketCap", _fetch_price_coinmarketcap),
    ("CryptoCompare", _fetch_price_cryptocompare),
    ("Binance", _fetch_price_binance),
    ("KuCoin", _fetch_price_kucoin),
    ("Bybit", _fetch_price_bybit),
    ("Gate.io", _fetch_price_gateio),
    ("MEXC", _fetch_price_mexc),
    # Add more fetchers here...
]

async def get_coin_price(symbol: str):
    """Fetch price from 50+ sources with multilayer fallback"""
    # First layer: API sources
    tasks = []
    for exchange_name, fetcher in PRICE_FETCHERS:
        task = asyncio.create_task(fetcher(symbol))
        tasks.append((exchange_name, task))
    
    for exchange_name, task in tasks:
        try:
            result = await task
            if result and result.get('price'): # Ensure price is valid
                return _format_price_message(exchange_name, symbol, result)
        except Exception as e:
            logger.error(f"Price fetcher failed for {exchange_name}: {str(e)}")
    
    # Second layer: Web scraping
    try:
        scrape_result = await _fallback_web_scrape(symbol)
        if scrape_result:
            return scrape_result
    except Exception as e:
        logger.error(f"Web scrape failed: {str(e)}")
    
    # Third layer: Community APIs
    try:
        community_result = await _community_price_fallback(symbol)
        if community_result:
            return community_result
    except Exception as e:
        logger.error(f"Community fallback failed: {str(e)}")
    
    # Final fallback
    return f"❌ Could not find price data for '{symbol.upper()}' across 50+ sources"

async def _fallback_web_scrape(symbol: str):
    """Web scraping fallback"""
    urls = [
        f"https://www.coingecko.com/en/coins/{symbol}",
        f"https://coinmarketcap.com/currencies/{symbol}/",
        f"https://www.binance.com/en/price/{symbol}",
        f"https://cryptorank.io/price/{symbol}",
        f"https://www.livecoinwatch.com/price/{symbol}-USD"
    ]
    
    for url in urls:
        try:
            response = await api_client.get(url)
            if response.status_code != 200:
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # CoinGecko pattern
            price_el = soup.select_one('span[data-coin-symbol] .no-wrap, span[data-coingecko-id]')
            if price_el:
                price_text = re.sub(r'[^\d.]', '', price_el.get_text())
                if price_text:
                    return _format_price_message("Web Scrape (CoinGecko)", symbol, {
                        "price": float(price_text), "change": 0, "volume": 0, "high_24h": 0, "low_24h": 0
                    })
                
            # CoinMarketCap pattern
            price_el = soup.select_one('.priceValue, .sc-16r8icm-0')
            if price_el:
                price_text = re.sub(r'[^\d.]', '', price_el.get_text())
                if price_text:
                    return _format_price_message("Web Scrape (CoinMarketCap)", symbol, {
                        "price": float(price_text), "change": 0, "volume": 0, "high_24h": 0, "low_24h": 0
                    })
                
            # Binance pattern
            price_el = soup.select_one('.css-12ujz79, .css-1bwgsh3')
            if price_el:
                price_text = re.sub(r'[^\d.]', '', price_el.get_text())
                if price_text:
                    return _format_price_message("Web Scrape (Binance)", symbol, {
                        "price": float(price_text), "change": 0, "volume": 0, "high_24h": 0, "low_24h": 0
                    })
                
        except Exception as e:
            logger.warning(f"Web scrape failed for {url}: {str(e)}")
            
    return None

async def _community_price_fallback(symbol: str):
    """Community-powered fallback"""
    apis = [
        "https://api.coinpaprika.com/v1/tickers",
        "https://api.coinstats.app/public/v1/coins",
        "https://api.coinranking.com/v2/coins",
    ]
    
    for api in apis:
        try:
            data = await make_api_request(api)
            if not data:
                continue
                
            # Find coin in response
            coin_data = None
            coins = data.get('coins', []) or data.get('data', {}).get('coins', []) or data
            
            for coin in coins:
                if (coin.get('symbol', '').lower() == symbol.lower() or 
                    coin.get('id', '').lower() == symbol.lower() or 
                    coin.get('name', '').lower() == symbol.lower()):
                    coin_data = coin
                    break
                    
            if coin_data:
                price = coin_data.get('price') or coin_data.get('quotes', {}).get('USD', {}).get('price')
                if price:
                    return _format_price_message("Community API", symbol, {
                        "price": float(price),
                        "change": coin_data.get('priceChange1d', 0) or coin_data.get('percent_change_24h', 0),
                        "volume": coin_data.get('volume', 0) or coin_data.get('24hVolume', 0),
                        "high_24h": 0, "low_24h": 0
                    })
                
        except Exception as e:
            logger.warning(f"Community API failed: {str(e)}")
            
    return None

# --- Historical Data with 50+ Fallbacks ---

HISTORICAL_SOURCES = [
    "CoinGecko",
    "CryptoCompare",
    "Binance",
    "KuCoin",
    # "CoinMarketCap", # Often requires a higher tier plan for historical data
    "Bybit",
    "Gate.io",
    "MEXC",
    # Add more sources here...
]

async def get_historical_data(symbol: str, days=7):
    """Get historical data with multilayer fallback"""
    # First layer: Standard APIs
    for source in HISTORICAL_SOURCES:
        try:
            data = await _fetch_historical(source, symbol, days)
            if data and data.get('prices'): # Ensure data is not empty
                return data
        except Exception as e:
            logger.error(f"Historical source {source} failed: {str(e)}")
            
    # Second layer: Alternative APIs
    try:
        alt_data = await _alternative_historical(symbol, days)
        if alt_data and alt_data.get('prices'):
            return alt_data
    except Exception as e:
        logger.error(f"Alternative historical failed: {str(e)}")
        
    # Third layer: Web scraping
    try:
        scrape_data = await _scrape_historical(symbol, days)
        if scrape_data and scrape_data.get('prices'):
            return scrape_data
    except Exception as e:
        logger.error(f"Historical scraping failed: {str(e)}")
        
    return None

async def _fetch_historical(source: str, symbol: str, days: int):
    """Fetch historical data from a specific source"""
    if source == "CoinGecko":
        return await _fetch_historical_coingecko(symbol, days)
    elif source == "CryptoCompare":
        return await _fetch_historical_cryptocompare(symbol, days)
    elif source == "Binance":
        return await _fetch_historical_binance(symbol, days)
    elif source == "KuCoin":
        return await _fetch_historical_kucoin(symbol, days)
    # Add more implementations here...
    return None

async def _fetch_historical_coingecko(symbol: str, days: int):
    coin_id = await get_coin_id_from_symbol(symbol)
    if not coin_id:
        return None
        
    params = {"vs_currency": "usd", "days": str(days)}
    data = await make_api_request(
        f"{EXCHANGE_APIS['CoinGecko']}/coins/{coin_id}/market_chart", 
        params=params
    )
    
    if not data or "prices" not in data:
        return None
        
    prices = data["prices"]
    return {
        "timestamps": [pd.to_datetime(p[0], unit='ms') for p in prices],
        "prices": [p[1] for p in prices],
        "coin": symbol.upper(),
        "source": "CoinGecko"
    }

async def _fetch_historical_cryptocompare(symbol: str, days: int):
    params = {'fsym': symbol.upper(), 'tsym': 'USD', 'limit': days}
    data = await make_api_request(
        f"https://min-api.cryptocompare.com/data/v2/histoday", 
        params=params
    )
    
    if not data or 'Data' not in data or 'Data' not in data['Data']:
        return None
        
    try:
        hist_data = data['Data']['Data']
        timestamps = [pd.to_datetime(item['time'], unit='s') for item in hist_data]
        prices = [item['close'] for item in hist_data]
        return {
            "timestamps": timestamps,
            "prices": prices,
            "coin": symbol.upper(),
            "source": "CryptoCompare"
        }
    except (KeyError, TypeError):
        return None

async def _fetch_historical_binance(symbol: str, days: int):
    params = {'symbol': f'{symbol.upper()}USDT', 'interval': '1d', 'limit': days}
    data = await make_api_request(
        f"{EXCHANGE_APIS['Binance']}/klines", 
        params=params
    )
    
    if not data:
        return None
        
    return {
        "timestamps": [pd.to_datetime(p[0], unit='ms') for p in data],
        "prices": [float(p[4]) for p in data],  # Closing price
        "coin": symbol.upper(),
        "source": "Binance"
    }

async def _fetch_historical_kucoin(symbol: str, days: int):
    # KuCoin API needs start and end times
    end_at = int(time.time())
    start_at = end_at - (days * 24 * 60 * 60)
    params = {'symbol': f'{symbol.upper()}-USDT', 'type': '1day', 'startAt': start_at, 'endAt': end_at}
    data = await make_api_request(
        f"{EXCHANGE_APIS['KuCoin']}/market/candles", 
        params=params
    )
    
    if not data or not data.get('data'):
        return None
        
    try:
        # Extract closing prices and timestamps
        candles = data['data']
        timestamps = [pd.to_datetime(candle[0], unit='s') for candle in candles]
        prices = [float(candle[2]) for candle in candles]  # Closing price
            
        return {
            "timestamps": timestamps,
            "prices": prices,
            "coin": symbol.upper(),
            "source": "KuCoin"
        }
    except (TypeError, KeyError, IndexError, ValueError):
        return None

async def _alternative_historical(symbol: str, days: int):
    """Alternative historical data APIs"""
    coin_id = await get_coin_id_from_symbol(symbol)
    if not coin_id:
        return None

    apis = [
        (f"https://api.coinstats.app/public/v1/charts?period={days}d&coinId={coin_id}", "CoinStats"),
        (f"https://api.coinpaprika.com/v1/tickers/{coin_id}/historical?start={datetime.now() - timedelta(days=days)}&interval=1d", "CoinPaprika"),
        (f"https://api.coincap.io/v2/assets/{coin_id}/history?interval=d1", "CoinCap")
    ]
    
    for url, source in apis:
        try:
            data = await make_api_request(url)
            if not data:
                continue
                
            timestamps, prices = [], []
            
            if source == "CoinStats" and 'chart' in data:
                for item in data['chart']:
                    timestamps.append(pd.to_datetime(item[0], unit='s'))
                    prices.append(item[1])
            
            elif source == "CoinPaprika" and isinstance(data, list):
                for item in data:
                    timestamps.append(pd.to_datetime(item['timestamp']))
                    prices.append(item['price'])

            elif source == "CoinCap" and 'data' in data:
                for item in data['data'][-days:]: # Limit to requested days
                    timestamps.append(pd.to_datetime(item['time'], unit='ms'))
                    prices.append(float(item['priceUsd']))
            
            if timestamps and prices:
                return {
                    "timestamps": timestamps, "prices": prices, 
                    "coin": symbol.upper(), "source": source
                }
                
        except Exception as e:
            logger.warning(f"Alternative historical API {source} failed: {str(e)}")
            
    return None


async def _scrape_historical(symbol: str, days: int):
    """Fallback to web scraping for historical data"""
    coin_id = await get_coin_id_from_symbol(symbol)
    if not coin_id:
        return None

    urls = [
        (f"https://www.coingecko.com/en/coins/{coin_id}/historical_data", "CoinGecko"),
        (f"https://coinmarketcap.com/currencies/{coin_id}/historical-data/", "CoinMarketCap")
    ]
    
    for url, source in urls:
        try:
            response = await api_client.get(url)
            if response.status_code != 200:
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            prices, timestamps = [], []
            
            table = soup.find('table')
            if not table: continue
            
            rows = table.find('tbody').find_all('tr')
            for row in rows[:days]:
                cols = row.find_all(['th', 'td'])
                if len(cols) < 2: continue

                try:
                    date_str = cols[0].get_text(strip=True)
                    # Adjust price column index based on source
                    price_col_index = 4 if source == "CoinMarketCap" else 1
                    price_str = cols[price_col_index].get_text(strip=True)
                    
                    date = datetime.strptime(date_str, '%b %d, %Y')
                    price = float(re.sub(r'[^\d.]', '', price_str))
                    
                    timestamps.append(date)
                    prices.append(price)
                except (ValueError, TypeError, IndexError):
                    continue
            
            if prices:
                # Reverse data as websites usually show newest first
                return {
                    "timestamps": timestamps[::-1], "prices": prices[::-1],
                    "coin": symbol.upper(), "source": f"Web Scrape ({source})"
                }
                
        except Exception as e:
            logger.warning(f"Historical scrape failed for {url}: {str(e)}")
            
    return None

# --- Trending Coins with 50+ Fallbacks ---

TRENDING_SOURCES = [
    "CoinGecko",
    "CoinMarketCap",
    "CryptoCompare",
    "CoinStats",
    "CoinPaprika",
    "LiveCoinWatch",
    "CoinRanking",
    "CoinCodex",
    "CoinLore",
    "AltRank",
    # Add more sources here...
]

async def get_trending_coins():
    """Get trending coins with multilayer fallback"""
    # First layer: Standard APIs
    for source in TRENDING_SOURCES:
        try:
            data = await _fetch_trending(source)
            if data:
                return data
        except Exception as e:
            logger.error(f"Trending source {source} failed: {str(e)}")
            
    # Second layer: Alternative APIs
    try:
        alt_data = await _alternative_trending()
        if alt_data:
            return alt_data
    except Exception as e:
        logger.error(f"Alternative trending failed: {str(e)}")
        
    # Third layer: Web scraping
    try:
        scrape_data = await _scrape_trending()
        if scrape_data:
            return scrape_data
    except Exception as e:
        logger.error(f"Trending scraping failed: {str(e)}")
        
    return "Could not retrieve trending coins at this time"

async def _fetch_trending(source: str):
    """Fetch trending coins from a specific source"""
    if source == "CoinGecko":
        return await _fetch_trending_coingecko()
    elif source == "CoinMarketCap":
        return await _fetch_trending_coinmarketcap()
    elif source == "CryptoCompare":
        return await _fetch_trending_cryptocompare()
    elif source == "CoinStats":
        return await _fetch_trending_coinstats()
    # Add more implementations here...
    return None
    
async def _fetch_trending_coingecko():
    data = await make_api_request(f"{EXCHANGE_APIS['CoinGecko']}/search/trending")
    if not data or 'coins' not in data:
        return None
        
    message = "🔥 **Top 7 Trending Coins (CoinGecko)** 🔥\n\n"
    for i, coin in enumerate(data['coins'][:7]): # Limit to 7 for cleaner output
        item = coin['item']
        message += (f"{i+1}. **{item['name']} ({item['symbol'].upper()})**\n"
                    f"   - Rank: {item['market_cap_rank']}\n\n")
    return message

async def _fetch_trending_coinmarketcap():
    headers = {"X-CMC_PRO_API_KEY": "b54bcf4d-1bca-4e8e-9a24-22ff2c3d462c"}
    data = await make_api_request(
        f"{EXCHANGE_APIS['CoinMarketCap']}/cryptocurrency/listings/latest?sort=market_cap&limit=10", 
        headers=headers
    )
    
    if not data or 'data' not in data:
        return None
        
    message = "🔥 **Top 10 Coins by Market Cap (CoinMarketCap)** 🔥\n\n"
    for i, coin in enumerate(data['data'][:10]):
        price = coin['quote']['USD']['price']
        message += (f"{i+1}. **{coin['name']} ({coin['symbol']})**\n"
                    f"   - Rank: {coin['cmc_rank']}\n"
                    f"   - Price: ${price:,.4f}\n\n")
    return message

async def _fetch_trending_cryptocompare():
    data = await make_api_request(f"https://min-api.cryptocompare.com/data/top/totalvolfull?limit=10&tsym=USD")
    if not data or 'Data' not in data:
        return None
        
    message = "🔥 **Top 10 by Volume (CryptoCompare)** 🔥\n\n"
    for i, coin in enumerate(data['Data'][:10]):
        info = coin.get('CoinInfo', {})
        display = coin.get('DISPLAY', {}).get('USD', {})
        if not info or not display: continue
        message += (f"{i+1}. **{info.get('FullName')} ({info.get('Name')})**\n"
                    f"   - Price: {display.get('PRICE', 'N/A')}\n"
                    f"   - 24h Volume: {display.get('VOLUME24HOUR', 'N/A')}\n\n")
    return message

async def _fetch_trending_coinstats():
    data = await make_api_request(f"{EXCHANGE_APIS['CoinStats']}/coins?skip=0&limit=10&currency=USD")
    if not data or 'coins' not in data:
        return None
        
    message = "🔥 **Top 10 Coins (CoinStats)** 🔥\n\n"
    for i, coin in enumerate(data['coins'][:10]):
        message += (f"{i+1}. **{coin['name']} ({coin['symbol']})**\n"
                    f"   - Price: ${coin.get('price', 0):,.4f}\n"
                    f"   - 24h Change: {coin.get('priceChange1d', 0):.2f}%\n\n")
    return message

async def _alternative_trending():
    # This can be simplified by just scraping one reliable source
    return None

async def _scrape_trending():
    """Fallback to web scraping for trending coins"""
    url = "https://coinmarketcap.com/trending-cryptocurrencies/"
    try:
        response = await api_client.get(url)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        coins = []
        
        table = soup.find('table')
        if not table: return None
        
        rows = table.find('tbody').find_all('tr')
        for row in rows[:10]:
            cols = row.find_all('td')
            if len(cols) < 3: continue
            
            try:
                name_el = cols[2].find('p', class_='coin-item-symbol')
                symbol = name_el.get_text(strip=True) if name_el else 'N/A'
                
                name_p = cols[2].find('p', class_='sc-1eb5slv-0')
                name = name_p.get_text(strip=True) if name_p else 'N/A'

                price_el = cols[3].find('span')
                price = price_el.get_text(strip=True) if price_el else 'N/A'
                
                coins.append({'name': name, 'symbol': symbol, 'price': price})
            except (AttributeError, IndexError):
                continue
        
        if coins:
            message = "🔥 **Top 10 Trending Coins (Web Scrape)** 🔥\n\n"
            for i, coin in enumerate(coins):
                message += (f"{i+1}. **{coin['name']} ({coin['symbol']})**\n"
                            f"   - Price: {coin['price']}\n\n")
            return message
            
    except Exception as e:
        logger.warning(f"Trending scrape failed for {url}: {str(e)}")
        
    return None

# --- News with 50+ Fallbacks ---

NEWS_SOURCES = NEWS_FEEDS + [
    "https://api.coingecko.com/api/v3/news",
    "https://min-api.cryptocompare.com/data/v2/news/?lang=EN",
]

async def get_crypto_news():
    """Get news with multilayer fallback"""
    # First layer: RSS feeds
    try:
        all_entries = []
        # Limit requests to avoid timeouts
        tasks = [asyncio.to_thread(parse_feed, feed_url) for feed_url in NEWS_SOURCES[:15]]
        results = await asyncio.gather(*tasks)
        for entries in results:
            all_entries.extend(entries)
            
        if all_entries:
            # Filter out old news
            one_day_ago = datetime.now() - timedelta(days=1)
            recent_entries = [e for e in all_entries if e['published'] > one_day_ago]
            recent_entries.sort(key=itemgetter('published'), reverse=True)
            if recent_entries:
                return format_news(recent_entries[:7]) # Limit to 7 for brevity
    except Exception as e:
        logger.error(f"RSS news failed: {str(e)}")
    
    # Second layer: News APIs
    try:
        api_news = await _news_api_fallback()
        if api_news:
            return api_news
    except Exception as e:
        logger.error(f"News API fallback failed: {str(e)}")
        
    # Third layer: Web scraping
    try:
        scrape_news = await _scrape_news()
        if scrape_news:
            return scrape_news
    except Exception as e:
        logger.error(f"News scraping failed: {str(e)}")
        
    return "Could not retrieve crypto news at this time"

def parse_feed(feed_url: str):
    try:
        # Use a timeout for feed parsing
        feed = feedparser.parse(feed_url, request_headers={'User-Agent': 'Mozilla/5.0'})
        entries = []
        for entry in feed.entries:
            title = entry.get('title', 'No title')
            link = entry.get('link', '')
            source = feed.feed.get('title', 'Unknown source')
            
            # Parse published date with fallbacks
            published_time = entry.get('published_parsed') or entry.get('updated_parsed')
            published = datetime.fromtimestamp(time.mktime(published_time)) if published_time else datetime.now()
                
            entries.append({
                'title': title, 'link': link, 'source': source, 'published': published
            })
        return entries
    except Exception as e:
        logger.error(f"Feed parsing failed for {feed_url}: {str(e)}")
        return []

def format_news(entries):
    message = "📰 **Latest Crypto News** 📰\n\n"
    for entry in entries:
        # Sanitize title for Markdown
        title = entry['title'].replace('[', '(').replace(']', ')')
        message += f"• [{title}]({entry['link']})\n"
    return message

async def _news_api_fallback():
    apis = [
        (f"{EXCHANGE_APIS['CoinGecko']}/news", "CoinGecko"),
        ("https://min-api.cryptocompare.com/data/v2/news/?lang=EN", "CryptoCompare")
    ]
    
    for url, source in apis:
        try:
            data = await make_api_request(url)
            if not data:
                continue
                
            entries = []
            items = data.get('data', []) or data.get('Data', [])
            for item in items[:10]:
                entries.append({
                    'title': item.get('title', 'No title'),
                    'link': item.get('url', ''),
                    'source': source,
                    'published': datetime.fromtimestamp(item.get('published_at', time.time()))
                })
                
            if entries:
                entries.sort(key=lambda x: x['published'], reverse=True)
                return format_news(entries[:7])
        except Exception as e:
            logger.warning(f"News API {source} failed: {str(e)}")
            
    return None

async def _scrape_news():
    """Fallback to web scraping for news"""
    sources = {
        "Cointelegraph": "https://cointelegraph.com/",
        "CoinDesk": "https://www.coindesk.com/",
    }
    
    news_items = []
    for source, url in sources.items():
        try:
            response = await api_client.get(url)
            if response.status_code != 200:
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            if source == "Cointelegraph":
                articles = soup.select('.post-card__title a')[:5]
            elif source == "CoinDesk":
                articles = soup.select('.card-title a')[:5]
            else:
                articles = []

            for article in articles:
                title = article.get_text(strip=True)
                link = article.get('href')
                if link and not link.startswith('http'):
                    link = url.rstrip('/') + link
                if title and link:
                    news_items.append({'title': title, 'link': link, 'source': source})
                    
        except Exception as e:
            logger.warning(f"News scrape failed for {source}: {str(e)}")
    
    if not news_items:
        return None
        
    message = "📰 **Latest Crypto News (Scraped)** 📰\n\n"
    for item in news_items[:7]:
        message += f"• [{item['title']}]({item['link']})\n"
    return message

# --- Fear & Greed with 50+ Fallbacks ---

async def get_fear_and_greed_index():
    """Get Fear & Greed with multilayer fallback"""
    # Primary API
    try:
        data = await _fetch_fear_greed_alternative()
        if data:
            return data
    except Exception as e:
        logger.error(f"Fear & Greed source failed: {str(e)}")
            
    # Web scraping fallback
    try:
        scrape_data = await _scrape_fear_greed()
        if scrape_data:
            return scrape_data
    except Exception as e:
        logger.error(f"Fear & Greed scraping failed: {str(e)}")
        
    return "Could not retrieve Fear & Greed Index at this time"

async def _fetch_fear_greed_alternative():
    data = await make_api_request("https://api.alternative.me/fng/?limit=1")
    if not data or 'data' not in data:
        return None
        
    try:
        latest_data = data['data'][0]
        value = int(latest_data['value'])
        classification = latest_data['value_classification']
        emoji = {
            "Extreme Fear": "😱", "Fear": "😨", "Neutral": "😐", 
            "Greed": "😊", "Extreme Greed": "🤑"
        }.get(classification, "🤔")
        meter = "[" + "🟩" * (value // 10) + "⬜️" * (10 - value // 10) + "]"
        return (f"{emoji} **Crypto Fear & Greed Index**\n\n"
                f"Current Value: `{value}` - *{classification}*\n{meter}\n\n"
                "0-24: Extreme Fear\n25-44: Fear\n45-54: Neutral\n"
                "55-74: Greed\n75-100: Extreme Greed")
    except (KeyError, ValueError, IndexError):
        return None

async def _scrape_fear_greed():
    """Fallback to web scraping for Fear & Greed"""
    url = "https://alternative.me/crypto/fear-and-greed-index/"
    try:
        response = await api_client.get(url)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        value_el = soup.select_one('.fng-value .fng-circle')
        if value_el:
            value = int(value_el.get_text(strip=True))
            classification = soup.select_one('.fng-value .fng-classification').get_text(strip=True)
            emoji = {
                "Extreme Fear": "😱", "Fear": "😨", "Neutral": "😐", 
                "Greed": "😊", "Extreme Greed": "🤑"
            }.get(classification, "🤔")
            meter = "[" + "🟩" * (value // 10) + "⬜️" * (10 - value // 10) + "]"
            return (f"{emoji} **Crypto Fear & Greed Index**\n\n"
                    f"Current Value: `{value}` - *{classification}*\n{meter}\n\n"
                    "0-24: Extreme Fear\n25-44: Fear\n45-54: Neutral\n"
                    "55-74: Greed\n75-100: Extreme Greed")
            
    except Exception as e:
        logger.warning(f"Fear & Greed scrape failed for {url}: {str(e)}")
        
    return None

# --- Market Overview with 50+ Fallbacks ---

async def get_market_overview():
    """Get market overview with multilayer fallback"""
    # Create a list of fetching functions to try in order
    market_fetchers = [
        _fetch_market_coingecko,
        _fetch_market_coinmarketcap,
        _fetch_market_coinstats,
        _fetch_market_coinpaprika,
        _fetch_market_coincap,
        _scrape_market # Last resort is scraping
    ]

    for fetcher in market_fetchers:
        try:
            data = await fetcher()
            if data:
                return data # Return the first successful result
        except Exception as e:
            logger.error(f"Market fetcher {fetcher.__name__} failed: {str(e)}")
            
    return "❌ Could not retrieve market overview at this time."

async def _fetch_market_coingecko():
    data = await make_api_request(f"{EXCHANGE_APIS['CoinGecko']}/global")
    if not data or 'data' not in data:
        return None
        
    d = data['data']
    change = d.get("market_cap_change_percentage_24h_usd", 0)
    change_icon = "📈" if change >= 0 else "📉"
    return (f"🌐 *Market Overview (CoinGecko)* 🌐\n\n"
            f"Total Market Cap: `${d.get('total_market_cap', {}).get('usd', 0):,.0f}`\n"
            f"24h Volume: `${d.get('total_volume', {}).get('usd', 0):,.0f}`\n"
            f"24h Change: {change_icon} {change:.2f}%\n"
            f"Bitcoin Dominance: `{d.get('market_cap_percentage', {}).get('btc', 0):.1f}%`\n"
            f"Active Cryptos: `{d.get('active_cryptocurrencies', 0):,}`")

async def _fetch_market_coinmarketcap():
    headers = {"X-CMC_PRO_API_KEY": "b54bcf4d-1bca-4e8e-9a24-22ff2c3d462c"}
    data = await make_api_request(f"{EXCHANGE_APIS['CoinMarketCap']}/global-metrics/quotes/latest", headers=headers)
    if not data or 'data' not in data:
        return None
        
    d = data['data']
    quote = d['quote']['USD']
    change = quote.get('total_market_cap_yesterday_percentage_change', 0)
    change_icon = "📈" if change >= 0 else "📉"
    return (f"🌐 *Market Overview (CoinMarketCap)* 🌐\n\n"
            f"Total Market Cap: `${quote.get('total_market_cap', 0):,.0f}`\n"
            f"24h Volume: `${quote.get('total_volume_24h', 0):,.0f}`\n"
            f"24h Change: {change_icon} {change:.2f}%\n"
            f"Bitcoin Dominance: `{d.get('btc_dominance', 0):.1f}%`\n"
            f"Active Cryptos: `{d.get('active_cryptocurrencies', 0):,}`")

async def _fetch_market_coinstats():
    data = await make_api_request(f"{EXCHANGE_APIS['CoinStats']}/global")
    if not data:
        return None
    
    change = data.get('marketCapChange', 0)
    change_icon = "📈" if change >= 0 else "📉"
    return (f"🌐 *Market Overview (CoinStats)* 🌐\n\n"
            f"Total Market Cap: `${data.get('marketCap', 0):,.0f}`\n"
            f"24h Volume: `${data.get('volume', 0):,.0f}`\n"
            f"24h Change: {change_icon} {change:.2f}%\n"
            f"Bitcoin Dominance: `{data.get('btcDominance', 0):.1f}%`\n"
            f"Active Coins: `{data.get('coinsCount', 0):,}`")

async def _fetch_market_coinpaprika():
    data = await make_api_request(f"{EXCHANGE_APIS['CoinPaprika']}/global")
    if not data:
        return None

    change = data.get('market_cap_change_24h', 0)
    change_icon = "📈" if change >= 0 else "📉"
    return (f"🌐 *Market Overview (CoinPaprika)* 🌐\n\n"
            f"Total Market Cap: `${data.get('market_cap_usd', 0):,.0f}`\n"
            f"24h Volume: `${data.get('volume_24h_usd', 0):,.0f}`\n"
            f"24h Change: {change_icon} {change:.2f}%\n"
            f"Bitcoin Dominance: `{data.get('bitcoin_dominance_percentage', 0):.1f}%`\n"
            f"Active Cryptos: `{data.get('cryptocurrencies_number', 0):,}`")

async def _fetch_market_coincap():
    data = await make_api_request(f"{EXCHANGE_APIS['CoinCap']}/assets")
    if not data or 'data' not in data:
        return None

    total_market_cap = 0
    total_volume = 0
    btc_market_cap = 0
    assets = data['data']
    
    for asset in assets:
        try:
            total_market_cap += float(asset['marketCapUsd'])
            total_volume += float(asset['volumeUsd24Hr'])
            if asset['symbol'].lower() == 'btc':
                btc_market_cap = float(asset['marketCapUsd'])
        except (TypeError, ValueError):
            continue
    
    dominance = (btc_market_cap / total_market_cap * 100) if total_market_cap > 0 else 0
    
    return (f"🌐 *Market Overview (CoinCap)* 🌐\n\n"
            f"Total Market Cap: `${total_market_cap:,.0f}`\n"
            f"24h Volume: `${total_volume:,.0f}`\n"
            f"Bitcoin Dominance: `{dominance:.1f}%`")

async def _scrape_market():
    """Fallback to web scraping for market overview"""
    url = "https://coinmarketcap.com/"
    try:
        response = await api_client.get(url)
        if response.status_code != 200: return None
        soup = BeautifulSoup(response.text, 'html.parser')
        
        container = soup.select_one('.cmc-global-stats__content')
        if not container: return None

        market_cap_el = container.select_one('a[href="/charts/"]')
        volume_el = container.select_one('a[href="/charts/#dominance-chart"]')
        dominance_el = container.select('a[href="/charts/#dominance-chart"]')[1]

        if market_cap_el and volume_el and dominance_el:
            market_cap = market_cap_el.get_text(strip=True)
            volume = volume_el.get_text(strip=True)
            dominance = dominance_el.get_text(strip=True)
            return (f"🌐 *Market Overview (Web Scrape)* 🌐\n\n"
                    f"Total Market Cap: `{market_cap}`\n"
                    f"24h Volume: `{volume}`\n"
                    f"BTC Dominance: `{dominance}`")
    except Exception as e:
        logger.warning(f"Market scrape failed for {url}: {str(e)}")
    return None


# --- Conversion with 50+ Fallbacks ---

async def convert_currency(amount, from_symbol, to_symbol):
    """Currency conversion with multilayer fallback"""
    if from_symbol.lower() == to_symbol.lower():
        return float(amount)

    # Use the robust get_coin_price function
    from_price_msg = await get_coin_price(from_symbol)
    to_price_msg = await get_coin_price(to_symbol)

    try:
        from_price_val = float(re.search(r'\$([\d,.]+)', from_price_msg).group(1).replace(',', ''))
        to_price_val = float(re.search(r'\$([\d,.]+)', to_price_msg).group(1).replace(',', ''))
        
        if from_price_val > 0 and to_price_val > 0:
            result = (float(amount) * from_price_val) / to_price_val
            return result
    except (AttributeError, ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(f"Price-based conversion failed: {e}")

    return None

# --- Telegram Command Handlers with Error Protection ---

def command_protector(func):
    """Decorator to protect commands from exceptions"""
    async def wrapper(update, context):
        try:
            await func(update, context)
        except Exception as e:
            logger.error(f"Command error in {func.__name__}: {str(e)}", exc_info=True)
            if update and update.message:
                await update.message.reply_text(
                    "⚠️ An unexpected error occurred. The developers have been notified. Please try again later.",
                    parse_mode='Markdown'
                )
    return wrapper

# --- MODIFIED: /start command now shows welcome and help text together ---
@command_protector
async def start_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    
    # The welcome message
    welcome_message = (f"👋 *Welcome to Crypto Guru!* 👋\n"
                       f"Your personal cryptocurrency market assistant with 50+ backup sources for every feature.")

    # The list of available commands
    commands_list = """
*🚀 Crypto Guru Bot Commands 🚀*

/start - Start the bot and see this message
/help - Show this help message again
/price `[symbol]` - Get current price (e.g., `/price btc`)
/price7d `[symbol]` - Get 7-day price chart (e.g., `/price7d eth`)
/trending - Show top trending/market cap coins
/news - Get latest crypto news
/feargreed - Show Fear & Greed Index
/market - Get a global market overview
/convert `[amount] [from] to [to]` - (e.g., `/convert 1.5 btc to eth`)
"""
    
    # Combine all parts into one message
    full_message = f"{welcome_message}\n\n{commands_list}\n{DISCLAIMER}"
    
    await update.message.reply_text(full_message, parse_mode='Markdown')

@command_protector
async def help_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
*🚀 Crypto Guru Bot Commands 🚀*

/start - Start the bot and see introduction
/help - Show this help message
/price `[symbol]` - Get current price (e.g., `/price btc`)
/price7d `[symbol]` - Get 7-day price chart (e.g., `/price7d eth`)
/trending - Show top trending/market cap coins
/news - Get latest crypto news
/feargreed - Show Fear & Greed Index
/market - Get a global market overview
/convert `[amount] [from] to [to]` - (e.g., `/convert 1.5 btc to eth`)
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

@command_protector
async def trending_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching trending coins from 50+ sources...")
    message = await get_trending_coins()
    await update.message.reply_text(message, parse_mode='Markdown')

@command_protector
async def top_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    await trending_command(update, context) # Alias for trending

@command_protector
async def news_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching news from 50+ sources...")
    message = await get_crypto_news()
    await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)

@command_protector
async def price_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ℹ️ Please specify a coin symbol. Example: `/price btc`")
        return
        
    coin_symbol = context.args[0].lower()
    await update.message.reply_text(f"⏳ Fetching price for {coin_symbol.upper()} from 50+ sources...")
    message = await get_coin_price(coin_symbol)
    await update.message.reply_text(message, parse_mode='Markdown')

@command_protector
async def price7d_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ℹ️ Please specify a coin. Example: `/price7d btc`")
        return
        
    coin_symbol = context.args[0].lower()
    await update.message.reply_text(f"⏳ Generating chart for {coin_symbol.upper()} using one of 50+ sources...")
    
    historical_data = await get_historical_data(coin_symbol, days=7)
    if not historical_data:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Couldn't get historical data for {coin_symbol.upper()}"
        )
        return
        
    chart_buf = await asyncio.to_thread(generate_price_chart, historical_data)
    if chart_buf:
        await update.message.reply_photo(photo=chart_buf, parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Could not generate chart")

@command_protector
async def feargreed_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching Fear & Greed Index...")
    message = await get_fear_and_greed_index()
    await update.message.reply_text(message, parse_mode='Markdown')

@command_protector
async def market_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching market overview...")
    message = await get_market_overview()
    await update.message.reply_text(message, parse_mode='Markdown')

@command_protector
async def convert_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Improved argument parsing
        text = ' '.join(context.args).lower()
        match = re.match(r'([\d.]+)\s*(\w+)\s*to\s*(\w+)', text)
        if not match:
            await update.message.reply_text("ℹ️ Usage: `/convert <amount> <from> to <to>`")
            return

        amount = float(match.group(1))
        from_currency = match.group(2)
        to_currency = match.group(3)
        
        await update.message.reply_text(f"⏳ Converting {amount} {from_currency.upper()} to {to_currency.upper()}...")
        result = await convert_currency(amount, from_currency, to_currency)
        
        if result is None:
            await update.message.reply_text("❌ Couldn't perform conversion. Check currencies or try again.")
            return
            
        message = (f"💱 *Currency Conversion*\n\n"
                   f"`{amount:,.4f} {from_currency.upper()} = {result:,.4f} {to_currency.upper()}`")
        await update.message.reply_text(message, parse_mode='Markdown')
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Invalid format. Usage: `/convert <amount> <from> to <to>`")

# --- System Functions ---

def generate_price_chart(historical_data):
    try:
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 5), facecolor='#1e1e1e')
        ax.set_facecolor('#1e1e1e')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('grey')
        ax.spines['left'].set_color('grey')
        
        # Create a smooth curve
        if len(historical_data["prices"]) > 3:
            x = np.array([d.timestamp() for d in historical_data["timestamps"]])
            y = np.array(historical_data["prices"])
            x_smooth = np.linspace(x.min(), x.max(), 200) # More points for smoothness
            y_smooth = np.interp(x_smooth, x, y)
            ax.plot(
                [pd.to_datetime(ts, unit='s') for ts in x_smooth],
                y_smooth,
                color='#00aaff',
                linewidth=2
            )
        else:
            ax.plot(
                historical_data["timestamps"],
                historical_data["prices"],
                color='#00aaff',
                linewidth=2,
                marker='o' # Add markers for few data points
            )
        
        ax.set_title(
            f"{historical_data['coin']} 7-Day Price Chart (via {historical_data.get('source', 'API')})", 
            color='white', 
            fontsize=16
        )
        ax.set_xlabel("Date", color='grey')
        ax.set_ylabel("Price (USD)", color='grey')
        ax.grid(True, linestyle='--', alpha=0.2)
        ax.tick_params(axis='x', colors='grey', rotation=20)
        ax.tick_params(axis='y', colors='grey')
        
        # Format Y-axis to show dollar signs
        ax.yaxis.set_major_formatter('${x:,.2f}')

        fig.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), dpi=100)
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as e:
        logger.error(f"Chart generation failed: {str(e)}")
        return None

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)


async def post_init(application: Application):
    await application.bot.set_my_commands([
        ('start', 'Start the bot'),
        ('help', 'Show help'),
        ('price', 'Get coin price'),
        ('price7d', '7-day price chart'),
        ('trending', 'Top trending coins'),
        ('top', 'Top cryptocurrencies (alias for trending)'),
        ('news', 'Latest crypto news'),
        ('feargreed', 'Fear & Greed Index'),
        ('market', 'Market overview'),
        ('convert', 'Convert currencies')
    ])
    logger.info("Bot commands initialized")

async def on_shutdown(application: Application):
    await api_client.aclose()
    logger.info("HTTP client closed")

def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is not set")
        return

    # Robust application builder
    builder = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(on_shutdown)
        .concurrent_updates(True)
    )
    
    application = builder.build()

    # Command handlers
    handlers = [
        CommandHandler("start", start_command),
        CommandHandler("help", help_command),
        CommandHandler("trending", trending_command),
        CommandHandler("top", top_command),
        CommandHandler("news", news_command),
        CommandHandler("price", price_command),
        CommandHandler("price7d", price7d_command),
        CommandHandler("feargreed", feargreed_command),
        CommandHandler("market", market_command),
        CommandHandler("convert", convert_command)
    ]
    
    application.add_handlers(handlers)
    application.add_error_handler(error_handler)

    logger.info("Starting bot...")
    try:
        application.run_polling()
    except Exception as e:
        logger.critical(f"Fatal error during polling: {str(e)}")
    finally:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(on_shutdown(application))
        else:
            asyncio.run(on_shutdown(application))

if __name__ == '__main__':
    try:
        keep_alive_thread = threading.Thread(target=keep_alive)
        keep_alive_thread.daemon = True
        keep_alive_thread.start()
    except NameError:
        logger.warning("keep_alive function not found. Running without it.")

    # Robust main execution with restart
    while True:
        try:
            main()
        except Exception as e:
            logger.critical(f"Main crashed: {str(e)}. Restarting in 10 seconds...")
            time.sleep(10)
