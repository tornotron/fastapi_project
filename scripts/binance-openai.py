import ccxt
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get API key and secret from environment variables
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

# Initialize the Binance exchange
binance = ccxt.binance(
    {
        "apiKey": api_key,
        "secret": api_secret,
    }
)

# Fetch the account balance
balance = binance.fetch_balance()

# Print the account balance
for currency, amount in balance["total"].items():
    if amount > 0:
        available = balance["free"][currency]
        print(f"{currency}: {amount}")
