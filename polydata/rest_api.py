import json
import requests

def get_market_details(slug):
    response = requests.get("https://gamma-api.polymarket.com/markets?slug=" + slug).json()
    ids = json.loads(response[0]['clobTokenIds'])
    expiration = response[0]['endDate']
    return ids[0], ids[1], expiration