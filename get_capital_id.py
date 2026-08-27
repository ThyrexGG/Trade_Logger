import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

LIVE_API_URL = "https://api-capital.backend-capital.com/api/v1"
DEMO_API_URL = "https://demo-api-capital.backend-capital.com/api/v1"

def get_account_ids():
    api_key = os.getenv("CAPITAL_API_KEY")
    email = os.getenv("CAPITAL_EMAIL")
    password = os.getenv("CAPITAL_PASSWORD")
    is_demo = os.getenv("CAPITAL_IS_DEMO", "true").lower() == "true"
    
    if not all([api_key, email, password]):
        print("❌ Error: Make sure CAPITAL_API_KEY, CAPITAL_EMAIL, and CAPITAL_PASSWORD are filled out in your .env file first!")
        return

    base_url = DEMO_API_URL if is_demo else LIVE_API_URL
    print(f"Connecting to Capital.com ({'Demo' if is_demo else 'Live'}) to fetch account IDs...")

    # Establish Session
    session = requests.Session()
    headers = {
        "X-CAP-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "identifier": email,
        "password": password
    }

    try:
        response = session.post(f"{base_url}/session", headers=headers, json=payload)
        if response.status_code != 200:
            print(f"❌ Auth Failed: {response.status_code} - {response.text}")
            return
            
        cst = response.headers.get("CST")
        security_token = response.headers.get("X-SECURITY-TOKEN")
        
        if not cst or not security_token:
            print("❌ Failed to retrieve session tokens from response headers.")
            return
            
        headers.update({
            "CST": cst,
            "X-SECURITY-TOKEN": security_token
        })
        
        # Call /accounts endpoint
        res = session.get(f"{base_url}/accounts", headers=headers)
        if res.status_code != 200:
            print(f"❌ Failed to fetch accounts: {res.status_code} - {res.text}")
            return
            
        data = res.json()
        accounts = data.get("accounts", [])
        
        if not accounts:
            print("⚠️ No accounts found.")
            return
            
        print("\n=== YOUR CAPITAL.COM ACCOUNT DETAILS ===")
        for acc in accounts:
            acc_id = acc.get("accountId")
            acc_name = acc.get("accountName", "Unnamed Account")
            acc_type = acc.get("accountType", "CFD")
            balance = acc.get("balance", {}).get("balance", 0.0)
            currency = acc.get("balance", {}).get("currency", "USD")
            
            print(f"\n📍 Account Name: {acc_name}")
            print(f"   👉 CAPITAL_ACCOUNT_ID = {acc_id}")
            print(f"   Balance: {balance} {currency} ({acc_type})")
        print("\n========================================")
        print("Copy the CAPITAL_ACCOUNT_ID value above and paste it into your .env file!")
        
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    get_account_ids()
