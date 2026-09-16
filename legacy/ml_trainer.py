import os
import pandas as pd
import numpy as np
from datetime import datetime
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import database

MODEL_PATH = os.path.join(os.path.dirname(__file__), "trade_model.pkl")
ENCODER_PATH = os.path.join(os.path.dirname(__file__), "symbol_encoder.pkl")

def map_symbol_to_yf(sym):
    sym = str(sym).upper()
    if "XAU" in sym or "GOLD" in sym: return "GC=F"
    if "BTC" in sym: return "BTC-USD"
    if "ETH" in sym: return "ETH-USD"
    if "SPX" in sym or "US500" in sym or "500" in sym: return "^GSPC"
    if "NAS" in sym or "US100" in sym or "100" in sym: return "^IXIC"
    if "US30" in sym or "DOW" in sym: return "^DJI"
    if "GER" in sym or "DAX" in sym: return "^GDAXI"
    if "USD" in sym or "EUR" in sym or "GBP" in sym or "JPY" in sym:
        return f"{sym}=X"
    return None

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def prepare_features(df):
    """Extracts features and simulates historical technical context via yfinance."""
    df = df.copy()
    
    # Target variable: 1 (Win Buy), -1 (Win Sell), 0 (Loss / No Edge)
    def determine_target(row):
        if row.get("net_profit", 0) > 0:
            return 1 if str(row.get("direction")).upper() == "BUY" else -1
        return 0
        
    df["target_class"] = df.apply(determine_target, axis=1)
    
    try:
        df["entry_dt"] = pd.to_datetime(df["entry_time"], errors="coerce")
        df["hour_of_day"] = df["entry_dt"].dt.hour.fillna(0)
        df["day_of_week"] = df["entry_dt"].dt.dayofweek.fillna(0)
        df["date_only"] = df["entry_dt"].dt.date
    except Exception:
        df["hour_of_day"] = 0
        df["day_of_week"] = 0
        df["date_only"] = None

    # Fetch daily context for all unique symbols to vectorize lookup
    import yfinance as yf
    
    df["daily_rsi"] = 50.0
    df["ema_spread"] = 0.0
    
    unique_symbols = df["symbol"].unique()
    for sym in unique_symbols:
        yf_sym = map_symbol_to_yf(sym)
        if not yf_sym: continue
        
        try:
            # Fetch 1 year of data prior to the latest trade
            history = yf.download(yf_sym, period="2y", progress=False)
            if history.empty: continue
            
            if isinstance(history.columns, pd.MultiIndex):
                history.columns = history.columns.droplevel(1)
            
            # Calculate Indicators
            close_prices = history['Close']
            history['RSI'] = calc_rsi(close_prices)
            history['EMA_20'] = close_prices.ewm(span=20, adjust=False).mean()
            history['EMA_50'] = close_prices.ewm(span=50, adjust=False).mean()
            history['EMA_Spread'] = (history['EMA_20'] - history['EMA_50']) / history['EMA_50'] * 100
            
            history.index = history.index.date
            
            # Map back to our trades
            mask = df["symbol"] == sym
            dates = df.loc[mask, "date_only"]
            
            # We want the indicator values from the *previous* close to avoid look-ahead bias
            for idx, date_val in dates.items():
                if pd.isna(date_val): continue
                # Get the last available row before or exactly on date_val
                past_data = history[history.index <= date_val]
                if not past_data.empty:
                    last_row = past_data.iloc[-1]
                    df.at[idx, "daily_rsi"] = last_row.get("RSI", 50.0)
                    df.at[idx, "ema_spread"] = last_row.get("EMA_Spread", 0.0)
        except Exception as e:
            import traceback
            print(f"ML Feature fetch failed for {sym}: {e}\n{traceback.format_exc()}")

    # Fill NaNs with neutral values
    df["daily_rsi"] = df["daily_rsi"].fillna(50.0)
    df["ema_spread"] = df["ema_spread"].fillna(0.0)
    
    return df

def train_personal_edge_model():
    """Trains a Random Forest classifier on closed trades for 3-class prediction."""
    df = database.get_closed_trades()
    
    if df.empty or len(df) < 10:
        return False, "Not enough closed trades to train a reliable model (Need at least 10)."

    df = prepare_features(df)
    
    # Encode symbols
    encoder = LabelEncoder()
    df["sym_encoded"] = encoder.fit_transform(df["symbol"].astype(str))
    
    # Features to train on
    features = ["hour_of_day", "day_of_week", "sym_encoded", "daily_rsi", "ema_spread"]
    X = df[features]
    y = df["target_class"]
    
    # Train the Random Forest
    clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, class_weight="balanced")
    clf.fit(X, y)
    
    # Save model and encoder
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(clf, f)
    with open(ENCODER_PATH, "wb") as f:
        pickle.dump(encoder, f)
        
    # Calculate accuracy on training set just for logging
    accuracy = clf.score(X, y)
    
    return True, f"Model trained successfully on {len(df)} trades. Training Accuracy: {accuracy*100:.1f}%"

def predict_directional_probabilities(symbol, current_time_utc=None):
    """
    Predicts mutually exclusive probabilities for BUY (1), SELL (-1), and NEUTRAL (0).
    """
    if not os.path.exists(MODEL_PATH) or not os.path.exists(ENCODER_PATH):
        # Attempt to train if not exists
        success, _ = train_personal_edge_model()
        if not success:
            return {"buy_prob": 0.0, "sell_prob": 0.0, "neutral_prob": 0.0, "confidence": "Low", "error": "Insufficient data to predict."}

    try:
        with open(MODEL_PATH, "rb") as f:
            clf = pickle.load(f)
        with open(ENCODER_PATH, "rb") as f:
            encoder = pickle.load(f)
    except Exception:
        return {"buy_prob": 0.0, "sell_prob": 0.0, "neutral_prob": 0.0, "confidence": "Low", "error": "Error loading model."}

    if current_time_utc is None:
        current_time_utc = datetime.utcnow()
        
    hour = current_time_utc.hour
    dow = current_time_utc.weekday()
    
    # Handle unknown symbols safely
    try:
        sym_encoded = encoder.transform([str(symbol)])[0]
    except ValueError:
        sym_encoded = 0 # Fallback for unknown symbol

    # Fetch live technicals for prediction with in-memory caching
    global _YF_TECH_CACHE
    if "_YF_TECH_CACHE" not in globals():
        _YF_TECH_CACHE = {}

    import time
    now_t = time.time()
    live_rsi = 50.0
    live_ema_spread = 0.0
    
    clean_sym = str(symbol).upper().strip()
    if clean_sym in _YF_TECH_CACHE:
        c_rsi, c_ema, c_time = _YF_TECH_CACHE[clean_sym]
        if now_t - c_time < 60.0:
            live_rsi = c_rsi
            live_ema_spread = c_ema
        else:
            del _YF_TECH_CACHE[clean_sym]

    if clean_sym not in _YF_TECH_CACHE:
        yf_sym = map_symbol_to_yf(symbol)
        if yf_sym:
            try:
                import yfinance as yf
                history = yf.download(yf_sym, period="2mo", progress=False)
                if not history.empty:
                    if isinstance(history.columns, pd.MultiIndex):
                        history.columns = history.columns.droplevel(1)
                        
                    close_prices = history['Close']
                    history['RSI'] = calc_rsi(close_prices)
                    history['EMA_20'] = close_prices.ewm(span=20, adjust=False).mean()
                    history['EMA_50'] = close_prices.ewm(span=50, adjust=False).mean()
                    history['EMA_Spread'] = (history['EMA_20'] - history['EMA_50']) / history['EMA_50'] * 100
                    last_row = history.iloc[-1]
                    if not pd.isna(last_row.get("RSI")): live_rsi = float(last_row["RSI"])
                    if not pd.isna(last_row.get("EMA_Spread")): live_ema_spread = float(last_row["EMA_Spread"])
                    _YF_TECH_CACHE[clean_sym] = (live_rsi, live_ema_spread, now_t)
            except Exception:
                _YF_TECH_CACHE[clean_sym] = (50.0, 0.0, now_t)

    # Prepare feature array matching training structure
    X_pred = pd.DataFrame([{
        "hour_of_day": hour,
        "day_of_week": dow,
        "sym_encoded": sym_encoded,
        "daily_rsi": live_rsi,
        "ema_spread": live_ema_spread
    }])

    # Get probability across all classes
    probs = clf.predict_proba(X_pred)[0]
    classes = clf.classes_
    
    prob_dict = {1: 0.0, -1: 0.0, 0: 0.0}
    for i, cls in enumerate(classes):
        prob_dict[cls] = float(probs[i])
        
    training_date = datetime.fromtimestamp(os.path.getmtime(MODEL_PATH)).strftime("%Y-%m-%d %H:%M UTC")
    
    buy_prob = round(float(prob_dict[1]) * 100, 1)
    sell_prob = round(float(prob_dict[-1]) * 100, 1)
    neutral_prob = round(float(prob_dict[0]) * 100, 1)
    
    max_p = max(buy_prob, sell_prob)
    conf = "HIGH" if max_p > 60 else ("MEDIUM" if max_p > 40 else "LOW")
    
    return {
        "buy_prob": buy_prob,
        "sell_prob": sell_prob,
        "neutral_prob": neutral_prob,
        "confidence": conf,
        "training_date": training_date,
        "features_used": ["hour_of_day", "day_of_week", "symbol", "daily_rsi", "ema_spread"],
        "error": None
    }
