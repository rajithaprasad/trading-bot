#+------------------------------------------------------------------+
#|                                    EURUSD_ULTIMATE_BOT.py       |
#|                                                   Your Name     |
#|                                             https://www.mql5.com |
#+------------------------------------------------------------------+
import MetaTrader5 as mt5
import pandas as pd
import ta
import time
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import json
import os
import requests
import threading

# =============================================
# 1. SETTINGS
# =============================================
SYMBOL = "EURUSD"
TIMEFRAME = mt5.TIMEFRAME_H4
SL_POINTS = 300  # 30 pips (Base SL)
TP_POINTS = 600  # 60 pips (Base TP)
BASE_LOT_SIZE = 0.1

# === INDICATOR PARAMETERS ===
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
EMA_FAST = 20
EMA_SLOW = 50
BB_PERIOD = 20
BB_STD = 2
ADX_PERIOD = 14

# === RISK MANAGEMENT ===
RISK_PER_TRADE = 0.02  # 2% risk per trade
MAX_LOT_SIZE = 1.0
MIN_LOT_SIZE = 0.01
MAX_POSITIONS = 1
MAX_DAILY_LOSS = 0.05  # 5% daily loss limit
MAX_CONSECUTIVE_LOSSES = 5

# === TRAILING STOP ===
TRAILING_START = 20  # Start trailing after 20 pips profit
TRAILING_STEP = 15   # Trail by 15 pips
BREAKEVEN_TRIGGER = 15  # Move to breakeven after 15 pips profit

# === BACKTESTING ===
BACKTEST_DAYS = 90

# === TELEGRAM ===
TELEGRAM_ENABLED = False
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
CHAT_ID = "YOUR_CHAT_ID_HERE"

# =============================================
# 2. TELEGRAM NOTIFICATIONS
# =============================================
def send_telegram_message(message):
    if not TELEGRAM_ENABLED:
        return False
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except:
        return False

# =============================================
# 3. PERFORMANCE TRACKER
# =============================================
class PerformanceTracker:
    def __init__(self):
        self.total_trades = 0
        self.win_trades = 0
        self.loss_trades = 0
        self.total_profit = 0.0
        self.daily_profit = 0.0
        self.consecutive_losses = 0
        self.max_consecutive_losses = 0
        self.today = datetime.now().date()
        self.trades_history = []
        
    def add_trade(self, trade_type, entry, sl, tp, result, profit_pips, reasons):
        self.total_trades += 1
        
        if result == "WIN":
            self.win_trades += 1
            self.total_profit += profit_pips
            self.daily_profit += profit_pips
            self.consecutive_losses = 0
        else:
            self.loss_trades += 1
            self.total_profit += profit_pips
            self.daily_profit += profit_pips
            self.consecutive_losses += 1
            if self.consecutive_losses > self.max_consecutive_losses:
                self.max_consecutive_losses = self.consecutive_losses
        
        # Check if new day
        current_date = datetime.now().date()
        if current_date != self.today:
            self.daily_profit = profit_pips if result == "WIN" else profit_pips
            self.today = current_date
        
        # Save trade
        self.trades_history.append({
            'timestamp': datetime.now().isoformat(),
            'type': trade_type,
            'entry': entry,
            'sl': sl,
            'tp': tp,
            'result': result,
            'profit_pips': profit_pips,
            'reasons': reasons
        })
        
        self.save_to_file()
        self.print_performance()
        
    def save_to_file(self):
        try:
            with open('performance.json', 'w') as f:
                json.dump({
                    'total_trades': self.total_trades,
                    'win_trades': self.win_trades,
                    'loss_trades': self.loss_trades,
                    'total_profit': self.total_profit,
                    'win_rate': self.get_win_rate(),
                    'max_consecutive_losses': self.max_consecutive_losses,
                    'history': self.trades_history[-100:]  # Last 100 trades
                }, f, indent=4)
        except:
            pass
    
    def get_win_rate(self):
        if self.total_trades == 0:
            return 0.0
        return (self.win_trades / self.total_trades) * 100
    
    def print_performance(self):
        print("\n" + "="*70)
        print("📊 PERFORMANCE TRACKER")
        print("="*70)
        print(f"📈 Total Trades: {self.total_trades}")
        print(f"✅ Win Trades: {self.win_trades}")
        print(f"❌ Loss Trades: {self.loss_trades}")
        print(f"🎯 Win Rate: {self.get_win_rate():.1f}%")
        print(f"💰 Total Profit: {self.total_profit:.2f} pips")
        print(f"📅 Today's Profit: {self.daily_profit:.2f} pips")
        print(f"⚠️ Consecutive Losses: {self.consecutive_losses}/{MAX_CONSECUTIVE_LOSSES}")
        print("="*70)
        
        # Daily loss limit check
        if self.daily_profit < -(MAX_DAILY_LOSS * 10000):
            print("🚨 DAILY LOSS LIMIT REACHED! Stopping for today.")
            return False
        return True
    
    def should_stop_trading(self):
        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            print(f"🚨 {MAX_CONSECUTIVE_LOSSES} consecutive losses! Stopping.")
            return True
        if self.daily_profit < -(MAX_DAILY_LOSS * 10000):
            print("🚨 Daily loss limit reached!")
            return True
        return False

# =============================================
# 4. NEWS FILTER
# =============================================
class NewsFilter:
    def __init__(self):
        # High Impact News Events (GMT Time)
        self.high_impact_news = {
            'NFP': {'day': 4, 'hour': 13, 'minute': 30},  # First Friday
            'CPI': {'hour': 13, 'minute': 30},
            'FOMC': {'hour': 19, 'minute': 0},
            'ECB': {'hour': 12, 'minute': 45},
            'GDP': {'hour': 13, 'minute': 30},
            'PMI': {'hour': 14, 'minute': 45},
            'Unemployment': {'hour': 13, 'minute': 30},
        }
        self.news_blackout_minutes = 30  # Don't trade 30 mins before/after
    
    def is_news_time(self):
        now = datetime.now()
        current_time = now.time()
        
        # Check if it's NFP day (first Friday)
        if now.weekday() == 4 and now.day <= 7:
            nfp_time = datetime.strptime("13:30", "%H:%M").time()
            if self._within_blackout(current_time, nfp_time):
                return True, "NFP News"
        
        # Check for other news events
        for news_name, news_time in self.high_impact_news.items():
            if news_name == 'NFP':
                continue
            event_time = datetime.strptime(f"{news_time.get('hour', 13)}:{news_time.get('minute', 30)}", "%H:%M").time()
            if self._within_blackout(current_time, event_time):
                return True, f"{news_name} News"
        
        return False, "No News"
    
    def _within_blackout(self, current, event):
        current_minutes = current.hour * 60 + current.minute
        event_minutes = event.hour * 60 + event.minute
        diff = abs(current_minutes - event_minutes)
        return diff <= self.news_blackout_minutes

# =============================================
# 5. DYNAMIC LOT SIZE
# =============================================
def calculate_dynamic_lot_size(account_balance, sl_points):
    """ගිණුම් ශේෂය අනුව Lot Size ගණනය කරන්න"""
    risk_amount = account_balance * RISK_PER_TRADE
    
    point = mt5.symbol_info(SYMBOL).point
    sl_distance = sl_points * point
    
    if sl_distance <= 0:
        return MIN_LOT_SIZE
    
    # Lot Size = Risk Amount / (SL Distance * 100000)
    lot_size = risk_amount / (sl_distance * 100000)
    lot_size = round(lot_size * 100) / 100
    lot_size = max(MIN_LOT_SIZE, min(lot_size, MAX_LOT_SIZE))
    
    # Ensure lot size is valid (step 0.01)
    lot_size = round(lot_size * 100) / 100
    
    return lot_size

# =============================================
# 6. MARKET STRUCTURE & TREND ANALYSIS
# =============================================
def analyze_market_structure(df, lookback=50):
    """
    Market Structure Analysis:
    - UPTREND, DOWNTREND, RANGING
    - Swing Highs, Swing Lows
    - Trend Lines
    """
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    
    # Find Swing Highs and Lows
    swing_highs = []
    swing_lows = []
    sensitivity = 5
    
    for i in range(sensitivity, len(highs) - sensitivity):
        if highs[i] == max(highs[i-sensitivity:i+sensitivity+1]):
            swing_highs.append((i, highs[i]))
        if lows[i] == min(lows[i-sensitivity:i+sensitivity+1]):
            swing_lows.append((i, lows[i]))
    
    # Determine Market Structure
    structure = "RANGING"
    
    if len(swing_lows) >= 3:
        # Check Higher Lows (Uptrend)
        higher_lows = all(swing_lows[i][1] < swing_lows[i+1][1] for i in range(len(swing_lows)-1))
        if higher_lows:
            structure = "UPTREND"
    
    if len(swing_highs) >= 3:
        # Check Lower Highs (Downtrend)
        lower_highs = all(swing_highs[i][1] > swing_highs[i+1][1] for i in range(len(swing_highs)-1))
        if lower_highs:
            structure = "DOWNTREND"
    
    # Check if both conditions exist (mixed)
    if structure == "RANGING":
        # Check ADX for trend strength
        adx = ta.trend.adx(df['high'], df['low'], df['close'], window=ADX_PERIOD)
        current_adx = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 20
        
        if current_adx > 30:
            if closes[-1] > closes[-10]:
                structure = "UPTREND"
            else:
                structure = "DOWNTREND"
    
    # Calculate trend strength
    trend_strength = 0
    if structure == "UPTREND":
        trend_strength = 1
    elif structure == "DOWNTREND":
        trend_strength = -1
    
    return {
        'structure': structure,
        'trend_strength': trend_strength,
        'swing_highs': swing_highs[-3:],
        'swing_lows': swing_lows[-3:],
        'adx': current_adx if 'current_adx' in locals() else 20
    }

# =============================================
# 7. RR RATIO ADJUSTER
# =============================================
def calculate_rr_ratio(market_structure, adx_value):
    """
    Market conditions අනුව RR Ratio ගණනය කරන්න
    """
    # Base RR Ratio
    base_rr = 2.0
    
    # Strong trend - Higher RR
    if market_structure['structure'] == "UPTREND" and adx_value > 30:
        return 3.0  # 1:3
    elif market_structure['structure'] == "DOWNTREND" and adx_value > 30:
        return 3.0  # 1:3
    
    # Medium trend - Standard RR
    elif adx_value > 25:
        return 2.0  # 1:2
    
    # Ranging market - Lower RR
    elif market_structure['structure'] == "RANGING":
        return 1.5  # 1:1.5
    
    # Weak trend - Conservative RR
    else:
        return 1.5  # 1:1.5

# =============================================
# 8. SUPPORT & RESISTANCE
# =============================================
def find_support_resistance(df, lookback=50, sensitivity=5):
    highs = df['high'].values
    lows = df['low'].values
    
    resistance_levels = []
    support_levels = []
    
    for i in range(sensitivity, len(highs) - sensitivity):
        if highs[i] == max(highs[i-sensitivity:i+sensitivity+1]):
            resistance_levels.append(highs[i])
    
    for i in range(sensitivity, len(lows) - sensitivity):
        if lows[i] == min(lows[i-sensitivity:i+sensitivity+1]):
            support_levels.append(lows[i])
    
    if support_levels:
        support_levels = sorted(set([round(x, 4) for x in support_levels]))[-5:]
    if resistance_levels:
        resistance_levels = sorted(set([round(x, 4) for x in resistance_levels]))[-5:]
    
    return support_levels, resistance_levels

# =============================================
# 9. INDICATOR FUNCTIONS
# =============================================
def get_indicators():
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 200)
    if rates is None:
        return None
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # RSI
    df['rsi'] = ta.momentum.rsi(df['close'], window=RSI_PERIOD)
    
    # EMA
    df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=EMA_FAST)
    df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=EMA_SLOW)
    
    # MACD
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_diff'] = macd.macd_diff()
    
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df['close'], window=BB_PERIOD, window_dev=BB_STD)
    df['bb_high'] = bb.bollinger_hband()
    df['bb_low'] = bb.bollinger_lband()
    
    # ADX
    df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'], window=ADX_PERIOD)
    
    # ATR
    df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
    
    current = {
        'rsi': df['rsi'].iloc[-1],
        'ema_fast': df['ema_fast'].iloc[-1],
        'ema_slow': df['ema_slow'].iloc[-1],
        'macd': df['macd'].iloc[-1],
        'macd_signal': df['macd_signal'].iloc[-1],
        'macd_diff': df['macd_diff'].iloc[-1],
        'bb_high': df['bb_high'].iloc[-1],
        'bb_low': df['bb_low'].iloc[-1],
        'adx': df['adx'].iloc[-1] if not pd.isna(df['adx'].iloc[-1]) else 20,
        'atr': df['atr'].iloc[-1] if not pd.isna(df['atr'].iloc[-1]) else 0.001,
        'close': df['close'].iloc[-1],
        'ema_fast_prev': df['ema_fast'].iloc[-2],
        'ema_slow_prev': df['ema_slow'].iloc[-2],
        'macd_prev': df['macd'].iloc[-2],
        'macd_signal_prev': df['macd_signal'].iloc[-2],
    }
    
    return current, df

def get_multi_timeframe_analysis():
    timeframes = [(mt5.TIMEFRAME_M15, "M15"), (mt5.TIMEFRAME_H1, "H1"), (mt5.TIMEFRAME_H4, "H4")]
    results = {}
    
    for tf, tf_name in timeframes:
        rates = mt5.copy_rates_from_pos(SYMBOL, tf, 0, 100)
        if rates is None:
            results[tf_name] = {'rsi': None, 'trend': 'N/A', 'signal': 'N/A'}
            continue
        
        df = pd.DataFrame(rates)
        rsi = ta.momentum.rsi(df['close'], window=RSI_PERIOD)
        current_rsi = rsi.iloc[-1]
        
        ema_fast = ta.trend.ema_indicator(df['close'], window=EMA_FAST)
        ema_slow = ta.trend.ema_indicator(df['close'], window=EMA_SLOW)
        trend = 'Bullish 🟢' if ema_fast.iloc[-1] > ema_slow.iloc[-1] else 'Bearish 🔴'
        
        macd = ta.trend.MACD(df['close'])
        macd_line = macd.macd().iloc[-1]
        signal_line = macd.macd_signal().iloc[-1]
        macd_signal = 'Bullish 🟢' if macd_line > signal_line else 'Bearish 🔴'
        
        signal = 'N/A'
        if current_rsi < RSI_OVERSOLD and ema_fast.iloc[-1] > ema_slow.iloc[-1]:
            signal = 'BUY'
        elif current_rsi > RSI_OVERBOUGHT and ema_fast.iloc[-1] < ema_slow.iloc[-1]:
            signal = 'SELL'
        
        results[tf_name] = {'rsi': current_rsi, 'trend': trend, 'macd_signal': macd_signal, 'signal': signal}
    
    return results

# =============================================
# 10. IMPROVED SIGNAL FILTERS
# =============================================
def check_buy_signal(data, df, mtf_signals, market_structure):
    signals = []
    
    # RSI Oversold
    if data['rsi'] < RSI_OVERSOLD:
        signals.append("RSI Oversold")
    elif 30 < data['rsi'] < 40:
        signals.append("RSI Rising from Oversold")
    
    # EMA Bullish
    if data['ema_fast'] > data['ema_slow'] and data['ema_fast_prev'] <= data['ema_slow_prev']:
        signals.append("EMA Bullish Crossover")
    elif data['ema_fast'] > data['ema_slow']:
        signals.append("EMA Uptrend")
    
    # MACD Bullish
    if data['macd'] > data['macd_signal'] and data['macd_prev'] <= data['macd_signal_prev']:
        signals.append("MACD Bullish Crossover")
    elif data['macd'] > data['macd_signal']:
        signals.append("MACD Bullish Momentum")
    
    # Bollinger Lower
    if data['close'] <= data['bb_low'] * 1.001:
        signals.append("Price near Lower BB")
    
    # Market Structure
    if market_structure['structure'] == "UPTREND":
        signals.append("Market Uptrend")
    
    # MTF Confirmation
    mtf_buy_count = sum(1 for tf, d in mtf_signals.items() if d['signal'] == 'BUY' or d['rsi'] < 35)
    if mtf_buy_count >= 2:
        signals.append(f"MTF Confirmation ({mtf_buy_count}/3)")
    
    # Support/Resistance
    support, resistance = find_support_resistance(df)
    for level in support:
        if abs(data['close'] - level) / data['close'] < 0.001:
            signals.append(f"Price near Support: {level:.4f}")
    
    return len(signals) >= 2, signals, support, resistance

def check_sell_signal(data, df, mtf_signals, market_structure):
    signals = []
    
    # RSI Overbought
    if data['rsi'] > RSI_OVERBOUGHT:
        signals.append("RSI Overbought")
    elif 60 < data['rsi'] < 70:
        signals.append("RSI Falling from Overbought")
    
    # EMA Bearish
    if data['ema_fast'] < data['ema_slow'] and data['ema_fast_prev'] >= data['ema_slow_prev']:
        signals.append("EMA Bearish Crossover")
    elif data['ema_fast'] < data['ema_slow']:
        signals.append("EMA Downtrend")
    
    # MACD Bearish
    if data['macd'] < data['macd_signal'] and data['macd_prev'] >= data['macd_signal_prev']:
        signals.append("MACD Bearish Crossover")
    elif data['macd'] < data['macd_signal']:
        signals.append("MACD Bearish Momentum")
    
    # Bollinger Upper
    if data['close'] >= data['bb_high'] * 0.999:
        signals.append("Price near Upper BB")
    
    # Market Structure
    if market_structure['structure'] == "DOWNTREND":
        signals.append("Market Downtrend")
    
    # MTF Confirmation
    mtf_sell_count = sum(1 for tf, d in mtf_signals.items() if d['signal'] == 'SELL' or d['rsi'] > 65)
    if mtf_sell_count >= 2:
        signals.append(f"MTF Confirmation ({mtf_sell_count}/3)")
    
    # Support/Resistance
    support, resistance = find_support_resistance(df)
    for level in resistance:
        if abs(data['close'] - level) / data['close'] < 0.001:
            signals.append(f"Price near Resistance: {level:.4f}")
    
    return len(signals) >= 2, signals, support, resistance

# =============================================
# 11. ORDER FUNCTIONS
# =============================================
def modify_order(ticket, sl, tp):
    """Existing Order Modify කරන්න"""
    try:
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": sl,
            "tp": tp,
        }
        result = mt5.order_send(request)
        return result.retcode == mt5.TRADE_RETCODE_DONE
    except:
        return False

def place_order(order_type, reasons, mtf_signals, sl_points, tp_points):
    symbol_info = mt5.symbol_info(SYMBOL)
    if symbol_info is None:
        return False
    
    point = symbol_info.point
    tick = mt5.symbol_info_tick(SYMBOL)
    
    # Calculate dynamic lot size
    account_balance = mt5.account_info().balance
    lot_size = calculate_dynamic_lot_size(account_balance, sl_points)
    
    if order_type == "BUY":
        price = tick.ask
        sl = price - sl_points * point
        tp = price + tp_points * point
        order_type_mt5 = mt5.ORDER_TYPE_BUY
        direction = "BUY 🟢"
    elif order_type == "SELL":
        price = tick.bid
        sl = price + sl_points * point
        tp = price - tp_points * point
        order_type_mt5 = mt5.ORDER_TYPE_SELL
        direction = "SELL 🔴"
    else:
        return False
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": lot_size,
        "type": order_type_mt5,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 123456,
        "comment": "EURUSD Ultimate Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"❌ Order Failed: {result.comment}")
        return False
    
    print(f"✅ {direction} Order placed!")
    print(f"   Entry: {price}, SL: {sl}, TP: {tp}")
    print(f"   Lot Size: {lot_size}, RR Ratio: {tp_points/sl_points:.1f}")
    print(f"📌 Reasons: {', '.join(reasons)}")
    
    # Save to journal
    save_trade_to_journal(order_type, price, sl, tp, reasons, mtf_signals)
    
    # Telegram notification
    message = f"""
🔔 <b>{direction} ORDER PLACED!</b>
📊 Symbol: {SYMBOL}
💰 Entry: {price}
🔴 SL: {sl}
🟢 TP: {tp}
📦 Lot: {lot_size}
📌 RR: {tp_points/sl_points:.1f}
📌 Reasons: {', '.join(reasons)}
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    send_telegram_message(message)
    
    return True

def save_trade_to_journal(order_type, price, sl, tp, reasons, mtf_signals):
    journal_file = "trading_journal.json"
    trade_entry = {
        'timestamp': datetime.now().isoformat(),
        'symbol': SYMBOL,
        'type': order_type,
        'price': price,
        'sl': sl,
        'tp': tp,
        'reasons': reasons,
        'mtf_signals': mtf_signals,
        'result': 'pending'
    }
    try:
        if os.path.exists(journal_file):
            with open(journal_file, 'r') as f:
                data = json.load(f)
        else:
            data = []
        data.append(trade_entry)
        with open(journal_file, 'w') as f:
            json.dump(data, f, indent=4)
    except:
        pass

def has_open_position():
    positions = mt5.positions_get(symbol=SYMBOL)
    return len(positions) > 0

def get_open_position():
    positions = mt5.positions_get(symbol=SYMBOL)
    if positions:
        return positions[0]
    return None

# =============================================
# 12. TRAILING STOP & BREAKEVEN MANAGEMENT
# =============================================
def manage_trailing_stop():
    """Trailing Stop Loss and Breakeven Management"""
    pos = get_open_position()
    if pos is None:
        return
    
    point = mt5.symbol_info(SYMBOL).point
    current_price = mt5.symbol_info_tick(SYMBOL).bid
    entry_price = pos.price_open
    current_sl = pos.sl
    current_tp = pos.tp
    
    if pos.type == mt5.POSITION_TYPE_BUY:
        profit_pips = (current_price - entry_price) / point
        
        # Breakeven
        if profit_pips >= BREAKEVEN_TRIGGER and current_sl < entry_price:
            new_sl = entry_price
            if modify_order(pos.ticket, new_sl, current_tp):
                print(f"🔒 SL moved to Breakeven ({profit_pips:.1f} pips profit)")
                send_telegram_message(f"🔒 {SYMBOL} SL moved to Breakeven")
        
        # Trailing Stop
        elif profit_pips >= TRAILING_START:
            new_sl = current_price - TRAILING_STEP * point
            if new_sl > current_sl:
                if modify_order(pos.ticket, new_sl, current_tp):
                    print(f"📈 Trailing SL updated to {new_sl:.5f} ({profit_pips:.1f} pips profit)")
        
    elif pos.type == mt5.POSITION_TYPE_SELL:
        profit_pips = (entry_price - current_price) / point
        
        # Breakeven
        if profit_pips >= BREAKEVEN_TRIGGER and current_sl > entry_price:
            new_sl = entry_price
            if modify_order(pos.ticket, new_sl, current_tp):
                print(f"🔒 SL moved to Breakeven ({profit_pips:.1f} pips profit)")
                send_telegram_message(f"🔒 {SYMBOL} SL moved to Breakeven")
        
        # Trailing Stop
        elif profit_pips >= TRAILING_START:
            new_sl = current_price + TRAILING_STEP * point
            if new_sl < current_sl:
                if modify_order(pos.ticket, new_sl, current_tp):
                    print(f"📉 Trailing SL updated to {new_sl:.5f} ({profit_pips:.1f} pips profit)")

# =============================================
# 13. SESSION FILTER
# =============================================
def is_good_trading_time():
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()
    
    if weekday >= 5:
        return False, "Weekend - Market Closed"
    
    # GMT+5:30 to GMT conversion
    gmt_hour = (hour - 5) % 24
    gmt_minute = (now.minute - 30) % 60
    current_gmt = gmt_hour + gmt_minute / 60.0
    
    # London Session: 08:00 - 16:00 GMT
    # NY Session: 13:00 - 21:00 GMT
    in_london = 8.0 <= current_gmt <= 16.0
    in_ny = 13.0 <= current_gmt <= 21.0
    
    if in_london and in_ny:
        return True, "London/NY Overlap (Best!)"
    elif in_london:
        return True, "London Session"
    elif in_ny:
        return True, "NY Session"
    else:
        return False, f"Outside Trading Hours (GMT: {current_gmt:.2f})"

# =============================================
# 14. BACKTESTING
# =============================================
def run_backtest():
    print("\n" + "="*70)
    print("📊 BACKTESTING RESULTS")
    print("="*70)
    
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, BACKTEST_DAYS * 4)
    if rates is None:
        print("❌ Backtest data failed")
        return None
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    print(f"📅 Period: {df['time'].min()} to {df['time'].max()}")
    print(f"📊 Total Candles: {len(df)}")
    
    # Indicators
    df['rsi'] = ta.momentum.rsi(df['close'], window=RSI_PERIOD)
    df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=EMA_FAST)
    df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=EMA_SLOW)
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    bb = ta.volatility.BollingerBands(df['close'], window=BB_PERIOD, window_dev=BB_STD)
    df['bb_high'] = bb.bollinger_hband()
    df['bb_low'] = bb.bollinger_lband()
    df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'], window=ADX_PERIOD)
    
    df['signal'] = 0
    support_levels, resistance_levels = find_support_resistance(df)
    
    for i in range(100, len(df)):
        current = {
            'close': df['close'].iloc[i],
            'rsi': df['rsi'].iloc[i],
            'ema_fast': df['ema_fast'].iloc[i],
            'ema_slow': df['ema_slow'].iloc[i],
            'macd': df['macd'].iloc[i],
            'macd_signal': df['macd_signal'].iloc[i],
            'bb_high': df['bb_high'].iloc[i],
            'bb_low': df['bb_low'].iloc[i],
            'ema_fast_prev': df['ema_fast'].iloc[i-1],
            'ema_slow_prev': df['ema_slow'].iloc[i-1],
            'macd_prev': df['macd'].iloc[i-1],
            'macd_signal_prev': df['macd_signal'].iloc[i-1],
        }
        
        buy_signals = []
        if current['rsi'] < RSI_OVERSOLD: buy_signals.append('RSI')
        if current['ema_fast'] > current['ema_slow'] and current['ema_fast_prev'] <= current['ema_slow_prev']:
            buy_signals.append('EMA')
        if current['macd'] > current['macd_signal'] and current['macd_prev'] <= current['macd_signal_prev']:
            buy_signals.append('MACD')
        if current['close'] <= current['bb_low'] * 1.001: buy_signals.append('BB')
        
        sell_signals = []
        if current['rsi'] > RSI_OVERBOUGHT: sell_signals.append('RSI')
        if current['ema_fast'] < current['ema_slow'] and current['ema_fast_prev'] >= current['ema_slow_prev']:
            sell_signals.append('EMA')
        if current['macd'] < current['macd_signal'] and current['macd_prev'] >= current['macd_signal_prev']:
            sell_signals.append('MACD')
        if current['close'] >= current['bb_high'] * 0.999: sell_signals.append('BB')
        
        if len(buy_signals) >= 2:
            df.loc[df.index[i], 'signal'] = 1
        elif len(sell_signals) >= 2:
            df.loc[df.index[i], 'signal'] = -1
    
    total_buy = len(df[df['signal'] == 1])
    total_sell = len(df[df['signal'] == -1])
    
    print(f"\n📈 Buy Signals: {total_buy}")
    print(f"📉 Sell Signals: {total_sell}")
    
    plot_with_support_resistance(df, support_levels, resistance_levels)
    return df

def plot_with_support_resistance(df, support, resistance):
    try:
        plt.figure(figsize=(14, 8))
        plt.plot(df['time'], df['close'], label='Price', color='black', linewidth=1)
        
        for i, level in enumerate(support):
            if level > 0:
                plt.axhline(y=level, color='green', linestyle='--', linewidth=1, label='Support' if i == 0 else '')
                plt.text(df['time'].iloc[-1], level, f' S: {level:.4f}', color='green', fontsize=8)
        
        for i, level in enumerate(resistance):
            if level > 0:
                plt.axhline(y=level, color='red', linestyle='--', linewidth=1, label='Resistance' if i == 0 else '')
                plt.text(df['time'].iloc[-1], level, f' R: {level:.4f}', color='red', fontsize=8)
        
        buy_signals = df[df['signal'] == 1]
        sell_signals = df[df['signal'] == -1]
        
        if len(buy_signals) > 0:
            plt.scatter(buy_signals['time'], buy_signals['close'], color='green', marker='^', s=100, label='BUY Signal')
        if len(sell_signals) > 0:
            plt.scatter(sell_signals['time'], sell_signals['close'], color='red', marker='v', s=100, label='SELL Signal')
        
        plt.title(f'{SYMBOL} - Ultimate Bot Backtest Results')
        plt.xlabel('Date')
        plt.ylabel('Price')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig('ultimate_backtest.png', dpi=150, bbox_inches='tight')
        print("📊 Chart saved as 'ultimate_backtest.png'")
    except Exception as e:
        print(f"⚠️ Chart creation failed: {e}")

# =============================================
# 15. MAIN FUNCTION
# =============================================
def print_analysis(data, support, resistance, mtf_signals, session_info, market_structure, rr_ratio):
    print("\n" + "="*70)
    print("📊 CURRENT MARKET ANALYSIS")
    print("="*70)
    print(f"💰 Price: {data['close']:.5f}")
    print(f"📈 RSI: {data['rsi']:.2f} ", end="")
    if data['rsi'] < 30: print("🔵 Oversold")
    elif data['rsi'] > 70: print("🔴 Overbought")
    else: print("🟡 Neutral")
    
    print(f"📊 EMA (20): {data['ema_fast']:.5f} | EMA (50): {data['ema_slow']:.5f} ", end="")
    print("🟢 Bullish" if data['ema_fast'] > data['ema_slow'] else "🔴 Bearish")
    
    print(f"📊 MACD: {data['macd']:.5f} | Signal: {data['macd_signal']:.5f} ", end="")
    print("🟢 Bullish" if data['macd'] > data['macd_signal'] else "🔴 Bearish")
    
    print(f"📊 Bollinger: Upper: {data['bb_high']:.5f} | Lower: {data['bb_low']:.5f}")
    print(f"📊 ADX: {data['adx']:.1f} | ATR: {data['atr']:.5f}")
    print(f"📊 Market Structure: {market_structure['structure']}")
    print(f"📊 RR Ratio: {rr_ratio:.1f}")
    
    if support: print(f"📊 Support: {[round(x, 4) for x in support[-3:]]}")
    if resistance: print(f"📊 Resistance: {[round(x, 4) for x in resistance[-3:]]}")
    
    print(f"\n⏰ {session_info}")
    
    print("\n📊 Multi-Timeframe Signals:")
    for tf, tf_data in mtf_signals.items():
        rsi_val = tf_data['rsi'] if tf_data['rsi'] else "N/A"
        print(f"   {tf}: RSI={rsi_val}, Trend={tf_data['trend']}, Signal={tf_data['signal']}")
    print("="*70)

def main():
    if not mt5.initialize():
        print("❌ MT5 initialize failed!")
        return
    
    print(f"✅ MT5 Connected. Account: {mt5.account_info().login}")
    print(f"📊 Trading {SYMBOL} on H4 timeframe...")
    print("🤖 ULTIMATE BOT STARTED!")
    print("📌 Features: Dynamic Lot, Trailing SL, Breakeven, News Filter, Performance Tracker")
    
    # Initialize components
    tracker = PerformanceTracker()
    news_filter = NewsFilter()
    
    # Run backtest
    print("\n📊 Running Backtest...")
    run_backtest()
    print("\n" + "="*70)
    print("🔴 LIVE TRADING STARTING 🔴")
    print("="*70 + "\n")
    
    last_trailing_check = time.time()
    
    try:
        while True:
            # Check session
            is_good, session_msg = is_good_trading_time()
            if not is_good:
                print(f"⏳ {session_msg}")
                time.sleep(900)
                continue
            
            # Check news
            is_news, news_msg = news_filter.is_news_time()
            if is_news:
                print(f"⏳ {news_msg} - Waiting...")
                time.sleep(600)
                continue
            
            # Check performance
            if tracker.should_stop_trading():
                print("🚨 Performance limit reached. Stopping for today.")
                break
            
            # Manage trailing stop for existing position
            if has_open_position():
                if time.time() - last_trailing_check > 10:  # Check every 10 seconds
                    manage_trailing_stop()
                    last_trailing_check = time.time()
                time.sleep(5)
                continue
            
            # Get data
            result = get_indicators()
            if result is None:
                print("❌ Data unavailable")
                time.sleep(60)
                continue
            
            data, df = result
            if pd.isna(data['rsi']) or pd.isna(data['ema_fast']):
                print("⏳ Data calculation failed")
                time.sleep(60)
                continue
            
            # Multi-timeframe
            mtf_signals = get_multi_timeframe_analysis()
            
            # Market Structure
            market_structure = analyze_market_structure(df)
            
            # Calculate RR Ratio
            rr_ratio = calculate_rr_ratio(market_structure, data['adx'])
            
            # Check signals
            buy_signal, buy_reasons, support, resistance = check_buy_signal(data, df, mtf_signals, market_structure)
            sell_signal, sell_reasons, support, resistance = check_sell_signal(data, df, mtf_signals, market_structure)
            
            print_analysis(data, support, resistance, mtf_signals, session_msg, market_structure, rr_ratio)
            
            if buy_signal and not sell_signal:
                print(f"\n🟢 **BUY SIGNAL DETECTED!** 🟢")
                print(f"📌 Reasons: {', '.join(buy_reasons)}")
                
                # Calculate SL and TP with dynamic RR
                sl_points = SL_POINTS
                tp_points = int(SL_POINTS * rr_ratio)
                
                if place_order("BUY", buy_reasons, mtf_signals, sl_points, tp_points):
                    # Will track performance on exit
                    pass
                
            elif sell_signal and not buy_signal:
                print(f"\n🔴 **SELL SIGNAL DETECTED!** 🔴")
                print(f"📌 Reasons: {', '.join(sell_reasons)}")
                
                sl_points = SL_POINTS
                tp_points = int(SL_POINTS * rr_ratio)
                
                if place_order("SELL", sell_reasons, mtf_signals, sl_points, tp_points):
                    pass
                
            else:
                print("\n🟡 **NO TRADE SIGNAL** 🟡")
                if len(buy_reasons) == 0 and len(sell_reasons) == 0:
                    print("📌 No indicators are giving a clear signal.")
                elif len(buy_reasons) == 1:
                    print(f"📌 Only 1 BUY signal: {buy_reasons[0]}")
                elif len(sell_reasons) == 1:
                    print(f"📌 Only 1 SELL signal: {sell_reasons[0]}")
                else:
                    print(f"📌 BUY: {', '.join(buy_reasons)}")
                    print(f"📌 SELL: {', '.join(sell_reasons)}")
            
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        mt5.shutdown()
        print("🔌 MT5 disconnected.")

if __name__ == "__main__":
    main()