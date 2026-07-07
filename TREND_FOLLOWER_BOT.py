#+------------------------------------------------------------------+
#|                                    TREND_FOLLOWER_BOT.py        |
#|                                                   Your Name     |
#|                                             https://www.mql5.com |
#+------------------------------------------------------------------+
import MetaTrader5 as mt5
import pandas as pd
import ta
import time
import numpy as np
from datetime import datetime
import json
import os

# =============================================
# 1. SETTINGS
# =============================================
SYMBOL = "EURUSD"
TIMEFRAME = mt5.TIMEFRAME_H1  # 1 Hour Chart
SL_POINTS = 300  # 30 pips (Base SL)
RISK_PER_TRADE = 0.02  # 2% risk per trade
MAX_LOT_SIZE = 1.0
MIN_LOT_SIZE = 0.01

# === TRAILING STOP ===
TRAILING_START = 20  # Start trailing after 20 pips profit
TRAILING_STEP = 15   # Trail by 15 pips

# === INDICATOR PARAMETERS ===
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
EMA_FAST = 20
EMA_SLOW = 50
BB_PERIOD = 20
BB_STD = 2
ADX_PERIOD = 14

# =============================================
# 2. PERFORMANCE TRACKER
# =============================================
class PerformanceTracker:
    def __init__(self):
        self.total_trades = 0
        self.win_trades = 0
        self.loss_trades = 0
        self.total_profit = 0.0
        self.consecutive_losses = 0
        
    def add_trade(self, result, profit_pips):
        self.total_trades += 1
        if result == "WIN":
            self.win_trades += 1
            self.total_profit += profit_pips
            self.consecutive_losses = 0
        else:
            self.loss_trades += 1
            self.total_profit += profit_pips
            self.consecutive_losses += 1
        
        self.print_performance()
    
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
        print(f"⚠️ Consecutive Losses: {self.consecutive_losses}")
        print("="*70)

# =============================================
# 3. INDICATOR FUNCTIONS
# =============================================
def get_indicators():
    """සියලුම Indicators ගණනය කරන්න"""
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 200)
    if rates is None:
        return None
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # === RSI ===
    df['rsi'] = ta.momentum.rsi(df['close'], window=RSI_PERIOD)
    
    # === EMA ===
    df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=EMA_FAST)
    df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=EMA_SLOW)
    
    # === MACD ===
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_diff'] = macd.macd_diff()
    
    # === Bollinger Bands ===
    bb = ta.volatility.BollingerBands(df['close'], window=BB_PERIOD, window_dev=BB_STD)
    df['bb_high'] = bb.bollinger_hband()
    df['bb_low'] = bb.bollinger_lband()
    df['bb_mid'] = bb.bollinger_mavg()
    
    # === ADX ===
    df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'], window=ADX_PERIOD)
    
    # Current values
    current = {
        'rsi': df['rsi'].iloc[-1],
        'ema_fast': df['ema_fast'].iloc[-1],
        'ema_slow': df['ema_slow'].iloc[-1],
        'macd': df['macd'].iloc[-1],
        'macd_signal': df['macd_signal'].iloc[-1],
        'macd_diff': df['macd_diff'].iloc[-1],
        'bb_high': df['bb_high'].iloc[-1],
        'bb_low': df['bb_low'].iloc[-1],
        'bb_mid': df['bb_mid'].iloc[-1],
        'adx': df['adx'].iloc[-1] if not pd.isna(df['adx'].iloc[-1]) else 20,
        'close': df['close'].iloc[-1],
        'ema_fast_prev': df['ema_fast'].iloc[-2],
        'ema_slow_prev': df['ema_slow'].iloc[-2],
        'macd_prev': df['macd'].iloc[-2],
        'macd_signal_prev': df['macd_signal'].iloc[-2],
    }
    
    return current, df

def get_multi_timeframe_analysis():
    """Timeframes 3ක් එකවර විශ්ලේෂණය කරන්න"""
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
        macd = ta.trend.MACD(df['close'])
        adx = ta.trend.adx(df['high'], df['low'], df['close'], window=ADX_PERIOD)
        current_adx = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 20
        
        # Determine Trend
        trend = "NEUTRAL"
        if ema_fast.iloc[-1] > ema_slow.iloc[-1] and macd.macd().iloc[-1] > macd.macd_signal().iloc[-1]:
            trend = "BULLISH 🟢"
        elif ema_fast.iloc[-1] < ema_slow.iloc[-1] and macd.macd().iloc[-1] < macd.macd_signal().iloc[-1]:
            trend = "BEARISH 🔴"
        
        # ADX Filter
        if current_adx < 20:
            trend = "RANGING 🟡"
        
        # Signal
        signal = 'N/A'
        if trend == "BULLISH 🟢":
            signal = 'BUY'
        elif trend == "BEARISH 🔴":
            signal = 'SELL'
        
        results[tf_name] = {
            'rsi': current_rsi,
            'trend': trend,
            'signal': signal,
            'adx': current_adx
        }
    
    return results

# =============================================
# 4. TREND DETECTION
# =============================================
def detect_current_trend(data, df, mtf_signals):
    """
    සියලුම Indicators භාවිතා කර Trend හඳුනාගන්න
    """
    trends = []
    signals = []
    
    # === 1. EMA Trend ===
    if data['ema_fast'] > data['ema_slow']:
        trends.append("EMA: Bullish")
        signals.append("EMA Bullish")
    else:
        trends.append("EMA: Bearish")
        signals.append("EMA Bearish")
    
    # === 2. MACD Trend ===
    if data['macd'] > data['macd_signal']:
        trends.append("MACD: Bullish")
        signals.append("MACD Bullish")
    else:
        trends.append("MACD: Bearish")
        signals.append("MACD Bearish")
    
    # === 3. Price vs EMA ===
    if data['close'] > data['ema_fast']:
        trends.append("Price > EMA20: Bullish")
        signals.append("Price Above EMA")
    else:
        trends.append("Price < EMA20: Bearish")
        signals.append("Price Below EMA")
    
    # === 4. RSI ===
    if data['rsi'] < 40:
        trends.append("RSI: Oversold -> Bullish Potential")
        signals.append("RSI Oversold")
    elif data['rsi'] > 60:
        trends.append("RSI: Overbought -> Bearish Potential")
        signals.append("RSI Overbought")
    else:
        trends.append("RSI: Neutral")
    
    # === 5. Bollinger Bands ===
    if data['close'] <= data['bb_low'] * 1.002:
        trends.append("Price near Lower BB: Bullish")
        signals.append("Near Lower BB")
    elif data['close'] >= data['bb_high'] * 0.998:
        trends.append("Price near Upper BB: Bearish")
        signals.append("Near Upper BB")
    else:
        trends.append("Price in BB Middle")
    
    # === 6. ADX (Trend Strength) ===
    if data['adx'] > 30:
        trends.append(f"ADX: Strong Trend ({data['adx']:.1f})")
        signals.append("Strong Trend")
    elif data['adx'] > 20:
        trends.append(f"ADX: Moderate Trend ({data['adx']:.1f})")
        signals.append("Moderate Trend")
    else:
        trends.append(f"ADX: Weak/Ranging ({data['adx']:.1f})")
        signals.append("No Trend")
    
    # === 7. Multi-Timeframe Confirmation ===
    bullish_tfs = sum(1 for tf, d in mtf_signals.items() if d['signal'] == 'BUY')
    bearish_tfs = sum(1 for tf, d in mtf_signals.items() if d['signal'] == 'SELL')
    
    if bullish_tfs >= 2:
        trends.append("MTF: Multiple Timeframes Bullish")
        signals.append("MTF Bullish")
    elif bearish_tfs >= 2:
        trends.append("MTF: Multiple Timeframes Bearish")
        signals.append("MTF Bearish")
    else:
        trends.append("MTF: Mixed Signals")
    
    # === Determine Final Trend ===
    bullish_count = sum(1 for s in signals if 'Bullish' in s or 'Oversold' in s or 'Above' in s)
    bearish_count = sum(1 for s in signals if 'Bearish' in s or 'Overbought' in s or 'Below' in s)
    
    # Consider ADX for confidence
    trend_confident = data['adx'] > 25
    
    if bullish_count > bearish_count and bullish_count >= 4 and trend_confident:
        final_trend = "STRONG_BULLISH"
        trend_reasons = [s for s in signals if 'Bullish' in s or 'Oversold' in s or 'Above' in s]
    elif bullish_count > bearish_count and bullish_count >= 3:
        final_trend = "BULLISH"
        trend_reasons = [s for s in signals if 'Bullish' in s or 'Oversold' in s or 'Above' in s]
    elif bearish_count > bullish_count and bearish_count >= 4 and trend_confident:
        final_trend = "STRONG_BEARISH"
        trend_reasons = [s for s in signals if 'Bearish' in s or 'Overbought' in s or 'Below' in s]
    elif bearish_count > bullish_count and bearish_count >= 3:
        final_trend = "BEARISH"
        trend_reasons = [s for s in signals if 'Bearish' in s or 'Overbought' in s or 'Below' in s]
    else:
        final_trend = "RANGING"
        trend_reasons = ["Mixed/No Clear Trend"]
    
    return final_trend, trend_reasons, trends

# =============================================
# 5. ORDER FUNCTIONS
# =============================================
def calculate_dynamic_lot_size(account_balance, sl_points):
    """ගිණුම් ශේෂය අනුව Lot Size ගණනය කරන්න"""
    risk_amount = account_balance * RISK_PER_TRADE
    
    point = mt5.symbol_info(SYMBOL).point
    sl_distance = sl_points * point
    
    if sl_distance <= 0:
        return MIN_LOT_SIZE
    
    lot_size = risk_amount / (sl_distance * 100000)
    lot_size = round(lot_size * 100) / 100
    lot_size = max(MIN_LOT_SIZE, min(lot_size, MAX_LOT_SIZE))
    lot_size = round(lot_size * 100) / 100
    
    return lot_size

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

def place_order(order_type, trend_reasons, sl_points, tp_points):
    """Market Order එකක් දාන්න"""
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
        "comment": "Trend Follower Bot",
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
    print(f"📌 Reasons: {', '.join(trend_reasons)}")
    
    # Save trade info
    save_trade_to_journal(order_type, price, sl, tp, trend_reasons, lot_size)
    
    return True

def save_trade_to_journal(order_type, price, sl, tp, reasons, lot_size):
    """Trade Journal එකට Save කරන්න"""
    journal_file = "trend_follower_journal.json"
    trade_entry = {
        'timestamp': datetime.now().isoformat(),
        'symbol': SYMBOL,
        'type': order_type,
        'price': price,
        'sl': sl,
        'tp': tp,
        'lot_size': lot_size,
        'reasons': reasons,
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
    """විවෘත Position එකක් තියෙනවද?"""
    positions = mt5.positions_get(symbol=SYMBOL)
    return len(positions) > 0

def get_open_position():
    """විවෘත Position එක ලබා ගන්න"""
    positions = mt5.positions_get(symbol=SYMBOL)
    if positions:
        return positions[0]
    return None

# =============================================
# 6. TRAILING STOP MANAGEMENT
# =============================================
def manage_trailing_stop():
    """
    Trailing Stop Loss - 20 pips profit වලදී SL Adjust කරයි
    """
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
        
        # Trailing Start: 20 pips profit
        if profit_pips >= TRAILING_START:
            new_sl = current_price - TRAILING_STEP * point
            if new_sl > current_sl:
                if modify_order(pos.ticket, new_sl, current_tp):
                    print(f"📈 Trailing SL updated to {new_sl:.5f} ({profit_pips:.1f} pips profit)")
                    # Log trailing update
                    log_trailing_update(pos.ticket, new_sl, profit_pips)
        
    elif pos.type == mt5.POSITION_TYPE_SELL:
        profit_pips = (entry_price - current_price) / point
        
        # Trailing Start: 20 pips profit
        if profit_pips >= TRAILING_START:
            new_sl = current_price + TRAILING_STEP * point
            if new_sl < current_sl:
                if modify_order(pos.ticket, new_sl, current_tp):
                    print(f"📉 Trailing SL updated to {new_sl:.5f} ({profit_pips:.1f} pips profit)")
                    log_trailing_update(pos.ticket, new_sl, profit_pips)

def log_trailing_update(ticket, new_sl, profit_pips):
    """Trailing Update Log කරන්න"""
    try:
        log_file = "trailing_log.json"
        entry = {
            'timestamp': datetime.now().isoformat(),
            'ticket': ticket,
            'new_sl': new_sl,
            'profit_pips': profit_pips
        }
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                data = json.load(f)
        else:
            data = []
        data.append(entry)
        with open(log_file, 'w') as f:
            json.dump(data, f, indent=4)
    except:
        pass

# =============================================
# 7. SESSION FILTER
# =============================================
def is_good_trading_time():
    """හොඳ වෙළඳාම් වේලාවද?"""
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()
    
    if weekday >= 5:
        return False, "Weekend - Market Closed"
    
    # GMT+5:30 to GMT conversion
    gmt_hour = (hour - 5) % 24
    gmt_minute = (now.minute - 30) % 60
    current_gmt = gmt_hour + gmt_minute / 60.0
    
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
# 8. MAIN FUNCTION
# =============================================
def print_trend_analysis(data, mtf_signals, final_trend, trend_reasons, all_trends):
    """Console Analysis Print කරන්න"""
    print("\n" + "="*70)
    print("📊 TREND ANALYSIS")
    print("="*70)
    print(f"💰 Price: {data['close']:.5f}")
    print(f"📈 RSI: {data['rsi']:.2f} ", end="")
    if data['rsi'] < 30: print("🔵 Oversold")
    elif data['rsi'] > 70: print("🔴 Overbought")
    else: print("🟡 Neutral")
    
    print(f"📊 EMA (20): {data['ema_fast']:.5f} | EMA (50): {data['ema_slow']:.5f}")
    print(f"📊 MACD: {data['macd']:.5f} | Signal: {data['macd_signal']:.5f}")
    print(f"📊 Bollinger: Upper: {data['bb_high']:.5f} | Lower: {data['bb_low']:.5f}")
    print(f"📊 ADX: {data['adx']:.1f}")
    
    print(f"\n📌 Final Trend: {final_trend}")
    print(f"📌 Reasons: {', '.join(trend_reasons)}")
    
    print("\n📊 All Indicator Signals:")
    for trend in all_trends[:7]:  # Show first 7 signals
        print(f"   • {trend}")
    
    print("\n📊 Multi-Timeframe:")
    for tf, d in mtf_signals.items():
        print(f"   {tf}: RSI={d['rsi']:.1f}, ADX={d['adx']:.1f}, Trend={d['trend']}")
    print("="*70)

def main():
    if not mt5.initialize():
        print("❌ MT5 initialize failed!")
        return
    
    print(f"✅ MT5 Connected. Account: {mt5.account_info().login}")
    print(f"📊 Trading {SYMBOL} on {TIMEFRAME} timeframe...")
    print("🤖 TREND FOLLOWER BOT STARTED!")
    print("📌 Features: All Indicators, Trend Detection, 1:2 RR, Trailing SL (20 pips)")
    print("📌 One Order at a Time!")
    
    # Initialize tracker
    tracker = PerformanceTracker()
    
    # Main loop
    order_placed = False
    last_trailing_check = time.time()
    
    try:
        while True:
            # Check session
            is_good, session_msg = is_good_trading_time()
            if not is_good:
                print(f"⏳ {session_msg}")
                time.sleep(900)
                continue
            
            # Check if position exists
            if has_open_position():
                # Manage trailing stop
                if time.time() - last_trailing_check > 10:  # Check every 10 seconds
                    manage_trailing_stop()
                    last_trailing_check = time.time()
                time.sleep(5)
                continue
            
            # Get indicators
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
            
            # Multi-timeframe analysis
            mtf_signals = get_multi_timeframe_analysis()
            
            # Detect trend
            final_trend, trend_reasons, all_trends = detect_current_trend(data, df, mtf_signals)
            
            print_trend_analysis(data, mtf_signals, final_trend, trend_reasons, all_trends)
            
            # Decide action based on trend
            if final_trend in ["STRONG_BULLISH", "BULLISH"] and not has_open_position():
                print(f"\n🟢 **{final_trend} TREND DETECTED!** 🟢")
                print(f"📌 Placing BUY order...")
                
                sl_points = SL_POINTS
                tp_points = int(SL_POINTS * 2.0)  # 1:2 RR
                
                place_order("BUY", trend_reasons, sl_points, tp_points)
                
            elif final_trend in ["STRONG_BEARISH", "BEARISH"] and not has_open_position():
                print(f"\n🔴 **{final_trend} TREND DETECTED!** 🔴")
                print(f"📌 Placing SELL order...")
                
                sl_points = SL_POINTS
                tp_points = int(SL_POINTS * 2.0)  # 1:2 RR
                
                place_order("SELL", trend_reasons, sl_points, tp_points)
                
            else:
                print(f"\n🟡 **{final_trend} - No Trade** 🟡")
                print("📌 Waiting for clear trend signal...")
                if "RANGING" in final_trend:
                    print("📌 Market is ranging. Wait for trend to establish.")
            
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        mt5.shutdown()
        print("🔌 MT5 disconnected.")

if __name__ == "__main__":
    main()