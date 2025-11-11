import sqlite3
import pandas as pd

conn = sqlite3.connect('/Users/rohan/Downloads/Virdhi_Captial_trading_system/banknifty_trading_system/scripts/data/banknifty_data.db')

# Check raw timestamps
df = pd.read_sql_query("SELECT timestamp FROM ohlcv WHERE timeframe='1min' LIMIT 5", conn)
print("Raw timestamps from DB:")
print(df)
print(f"\nType: {df['timestamp'].dtype}")
print(f"Values: {df['timestamp'].values}")

# Try different conversions
df_test = pd.read_sql_query("SELECT * FROM ohlcv WHERE timeframe='1min' LIMIT 5", conn)
print("\n--- Trying unit='s':")
print(pd.to_datetime(df_test['timestamp'], unit='s'))

print("\n--- Trying unit='ms':")
print(pd.to_datetime(df_test['timestamp'], unit='ms'))

conn.close()