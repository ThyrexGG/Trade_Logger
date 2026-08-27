# Custom Trade Logger: Instructions

This guide explains how to start and run the local trading journal dashboard web interface, and how to trigger account synchronization.

---

## 1. Run the Web Dashboard

To run the Streamlit dashboard web interface locally, open your command terminal in the project directory (`C:\Users\Asus\Desktop\Trade_Logger`) and execute:

```bash
streamlit run app.py
```

Once executed, the terminal will display the local network addresses. The dashboard will automatically open in your default web browser at:
* **URL:** [http://localhost:8502](http://localhost:8502) (or [http://localhost:8501](http://localhost:8501))

---

## 2. Syncing Your Accounts

You can synchronize your trades directly inside the dashboard using the **Sync MT5** and **Sync Capital** buttons inside the top panel card.

Alternatively, you can trigger synchronization from the terminal:

### Sync MetaTrader 5 (MT5)
To extract new deals from MetaTrader 5 and reconstruct them into closed trades:
```bash
python mt5_sync.py
```

### Sync Capital.com
To fetch your transactions and activities day-by-day from the Capital.com REST API:
```bash
python capital_sync.py
```

---

## Prerequisites (One-time Setup)

If you are setting this up on a new device, ensure the dependencies are installed:
```bash
pip install -r requirements.txt
```
