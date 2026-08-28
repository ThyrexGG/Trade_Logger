import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
print(f"Connecting to Supabase: {db_url.split('@')[1] if '@' in db_url else db_url}")

conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute("SELECT version();")
print("PostgreSQL Version:", cur.fetchone())
conn.close()
print("Connection test successful!")
