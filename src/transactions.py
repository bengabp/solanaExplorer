import json
import time

import httpx
from datetime import datetime, timedelta
from pymongo.errors import DuplicateKeyError
from src.models import Transaction
from src.config import init_db, logger
import platform


def compute_timestamp(timestamp: int):
    try:
        _timestamp = timestamp
        _date = datetime.fromtimestamp(_timestamp)
    except OSError:
        _timestamp = timestamp / 1000
        _date = datetime.fromtimestamp(_timestamp)
    return _date, _timestamp


def get_transaction_coins_for_x_days(account_hash: str, last_x_days: int = 7):
    timeout = 60 * 10
    current_date = datetime.today()
    last_x_days_date = current_date - timedelta(days=last_x_days + 1)

    loop = True
    offset = 0
    limit = 30

    tokens_traded = set()

    headers = {
        'authority': 'multichain-api.birdeye.so',
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
        'agent-id': '18b2d1c0-e2fc-46ca-8a25-9ea14378e9e0',
        'cf-be': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE3MDc3NjE3MDMsImV4cCI6MTcwNzc2MjAwM30.xBDaGBD4403Ozcfya3bhCBFOMu6wipbiFSZE8-FXu7c',
        'origin': 'https://birdeye.so',
        'referer': 'https://birdeye.so/',
        'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    }

    while loop:
        params = {
            'address': account_hash,
            "offset": offset,
            "limit": limit
        }

        url = "https://multichain-api.birdeye.so/solana/trader_profile/trader_txs"
        response = httpx.get(url, params=params, headers=headers, timeout=timeout)
        if response.status_code in [200]:
            json_data = response.json()
            if json_data:
                if json_data.get("statusCode") == 200 and json_data.get("success"):
                    _data = json_data.get("data", {})
                    if _data:
                        has_next = _data.get("hasNext", False)
                        transactions = _data.get("items", [])
                        logger.info(f"Saving {len(transactions)} transactions for {account_hash} [{offset}]")
                        for transaction in transactions:
                            block_time = transaction["blockTime"]
                            _transaction_datetime, _timestamp = compute_timestamp(block_time)

                            # Only process transactions within last_x_days :
                            if _transaction_datetime - timedelta(days=2) >= last_x_days_date:
                                transaction["timestamp"] = _timestamp
                                transaction["account"] = account_hash
                                transaction.pop("blockTime", None)
                                sorted_int = transaction.pop("sortedIns", [])
                                for token in transaction.pop("tokenChange", []):
                                    tokens_traded.add(f"{token['address']}_____{token['symbol']}")
                            else:
                                loop = False
                                logger.info(f"All transactions for last {last_x_days} days complete")
                                break
                        if has_next:
                            offset += limit
                        else:
                            logger.info("No next results ...")
                            loop = False
                else:
                    logger.info(f"Request unsuccessful => {json_data}")
                    loop = True
        elif response.status_code == 429:
            logger.info("Too many requests .. sleeping for some time ...")
            time.sleep(60)

    # Get transaction data of each token filtering by account hash on radium pool:
    tokens_traded = list(tokens_traded)
    logger.info(f"Total tokens traded within last {last_x_days} days for account [{account_hash} => {len(tokens_traded)}")
    print(tokens_traded)


init_db([Transaction])
get_transaction_coins_for_x_days("2bhkQ6uVn32ddiG4Fe3DVbLsrExdb3ubaY6i1G4szEmq")