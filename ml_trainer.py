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

def prepare_features(df):
    """Extracts features from the raw trades dataframe."""
    df = df.copy()
    
    # Target variable: 1 (Win Buy), -1 (Win Sell), 0 (Loss / No Edge)
    def determine_target(row):
        if row.get("net_profit", 0) > 0:
            return 1 if str(row.get("direction")).upper() == "BUY" else -1
        return 0
        
    df["target_class"] = df.apply(determine_target, axis=1)
    
    # Features: Temporal patterns (Time of Day, Day of Week)
    try:
        df["entry_dt"] = pd.to_datetime(df["entry_time"], errors="coerce")
        df["hour_of_day"] = df["entry_dt"].dt.hour.fillna(0)
        df["day_of_week"] = df["entry_dt"].dt.dayofweek.fillna(0)
    except Exception:
        df["hour_of_day"] = 0
        df["day_of_week"] = 0

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
    features = ["hour_of_day", "day_of_week", "sym_encoded"]
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

    # Prepare feature array matching training structure
    X_pred = pd.DataFrame([{
        "hour_of_day": hour,
        "day_of_week": dow,
        "sym_encoded": sym_encoded
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
        "features_used": ["hour_of_day", "day_of_week", "symbol"],
        "error": None
    }
