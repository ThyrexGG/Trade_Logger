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
    
    # Target variable: Win (1) or Loss (0)
    if "net_profit" in df.columns:
        df["is_win"] = (df["net_profit"] > 0).astype(int)
    
    # Feature 1: Direction (BUY=1, SELL=0)
    df["dir_encoded"] = (df["direction"].str.upper() == "BUY").astype(int)
    
    # Feature 2 & 3: Temporal patterns (Time of Day, Day of Week)
    try:
        df["entry_dt"] = pd.to_datetime(df["entry_time"], errors="coerce")
        df["hour_of_day"] = df["entry_dt"].dt.hour.fillna(0)
        df["day_of_week"] = df["entry_dt"].dt.dayofweek.fillna(0)
    except Exception:
        df["hour_of_day"] = 0
        df["day_of_week"] = 0

    # Feature 4: Volume
    df["vol_feature"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.01)

    return df

def train_personal_edge_model():
    """Trains a Random Forest classifier on closed trades."""
    df = database.get_closed_trades()
    
    if df.empty or len(df) < 10:
        return False, "Not enough closed trades to train a reliable model (Need at least 10)."

    df = prepare_features(df)
    
    # Encode symbols
    encoder = LabelEncoder()
    df["sym_encoded"] = encoder.fit_transform(df["symbol"].astype(str))
    
    # Features to train on
    features = ["dir_encoded", "hour_of_day", "day_of_week", "vol_feature", "sym_encoded"]
    X = df[features]
    y = df["is_win"]
    
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

def predict_setup_probability(symbol, direction, volume, current_time_utc=None):
    """
    Predicts the probability of a trade being a winner based on historical personal data.
    """
    if not os.path.exists(MODEL_PATH) or not os.path.exists(ENCODER_PATH):
        # Attempt to train if not exists
        success, _ = train_personal_edge_model()
        if not success:
            return None, "Insufficient data to predict."

    try:
        with open(MODEL_PATH, "rb") as f:
            clf = pickle.load(f)
        with open(ENCODER_PATH, "rb") as f:
            encoder = pickle.load(f)
    except Exception:
        return None, "Error loading model."

    if current_time_utc is None:
        current_time_utc = datetime.utcnow()
        
    dir_encoded = 1 if str(direction).upper() == "BUY" else 0
    hour = current_time_utc.hour
    dow = current_time_utc.weekday()
    vol = float(volume)
    
    # Handle unknown symbols safely
    try:
        sym_encoded = encoder.transform([str(symbol)])[0]
    except ValueError:
        sym_encoded = 0 # Fallback for unknown symbol

    # Prepare feature array matching training structure
    X_pred = pd.DataFrame([{
        "dir_encoded": dir_encoded,
        "hour_of_day": hour,
        "day_of_week": dow,
        "vol_feature": vol,
        "sym_encoded": sym_encoded
    }])

    # Get probability of class 1 (Win)
    prob = clf.predict_proba(X_pred)[0][1]
    
    return prob, "Success"
