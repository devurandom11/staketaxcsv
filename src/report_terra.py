
"""
usage: python3 report_terra.py <walletaddress> [--format all|cointracking|koinly|..]

Prints transactions and writes CSV(s) to _reports/LUNA*.csv


Notes:
    * https://fcd.terra.dev/swagger
    * https://lcd.terra.dev/swagger/
    * https://docs.figment.io/network-documentation/terra/enriched-apis
"""

import logging
import json
import os
import pprint

from common.Cache import Cache
from common.Exporter import Exporter
from common import report_util
from terra.config_terra import localconfig
from terra.api_search_figment import SearchAPIFigment, LIMIT_FIGMENT
from terra.api_fcd import FcdAPI, LIMIT_FCD
import terra.processor
from terra.ProgressTerra import ProgressTerra, SECONDS_PER_TX
from settings_csv import TICKER_LUNA
from common.ErrorCounter import ErrorCounter
from settings_csv import TERRA_FIGMENT_KEY

MAX_TRANSACTIONS = 5000
MAX_QUERIES = int(MAX_TRANSACTIONS / LIMIT_FCD)


def main():
    wallet_address, format, txid, options = report_util.parse_args()
    readOptions(options)

    if txid:
        exporter = txone(wallet_address, txid)
        exporter.export_print()
    else:
        exporter = txhistory(wallet_address, job=None)
        report_util.run_exports(TICKER_LUNA, wallet_address, exporter, format)


def readOptions(options):
    if options:
        # Check for options with non-default values
        if options.get("debug") is True:
            localconfig.debug = True
        if options.get("cache") is True:
            localconfig.cache = True
        if options.get("minor_rewards") is True:
            localconfig.minor_rewards = True


def wallet_exists(wallet_address):
    if not wallet_address.startswith("terra"):
        return False
    data = SearchAPIFigment.get_txs(wallet_address, limit=2)
    return len(data) > 0


def txone(wallet_address, txid):
    data = FcdAPI.get_tx(txid)
    print("\ndebug data:")
    pprint.pprint(data)
    print("")

    exporter = Exporter(wallet_address)
    terra.processor.process_tx(wallet_address, data, exporter)
    print("")
    return exporter


def estimate_duration(wallet_address):
    return SECONDS_PER_TX * _num_txs(wallet_address)


def _num_txs(wallet_address):
    num_txs = 0
    for i in range(MAX_QUERIES):
        logging.info("estimate_duration() loop num_txs=%s", num_txs)

        data = SearchAPIFigment.get_txs(wallet_address, offset=num_txs)
        num_txs += len(data)

        if len(data) < LIMIT_FIGMENT:
            break

    return num_txs


def txhistory(wallet_address, job=None, options=None):
    progress = ProgressTerra()

    if options:
        readOptions(options)
    if job:
        localconfig.job = job
        localconfig.cache = True
    if localconfig.cache:
        localconfig.currency_addresses = Cache().get_terra_currency_addresses()
        logging.info("Loaded terra_currency_addresses from cache ...")
    if TERRA_FIGMENT_KEY:
        # Optional: Fetch count of transactions to estimate progress more accurately later
        num_txs = _num_txs(wallet_address)
        progress.set_estimate(num_txs)
        logging.info("num_txs=%s", num_txs)

    # Retrieve data
    elems = _get_txs(wallet_address, progress)
    elems.sort(key=lambda elem: elem["timestamp"])

    # Create rows for CSV
    exporter = Exporter(wallet_address)
    terra.processor.process_txs(wallet_address, elems, exporter, progress)

    # Log error stats if exists
    ErrorCounter.log(TICKER_LUNA, wallet_address)

    if localconfig.cache:
        Cache().set_terra_currency_addresses(localconfig.currency_addresses)
    return exporter


def _get_txs(wallet_address, progress):
    # Debugging only: when --debug flag set, read from cache file
    DEBUG_FILE = "_reports/debugterra.{}.json".format(wallet_address)
    if localconfig.debug and os.path.exists(DEBUG_FILE):
        with open(DEBUG_FILE, 'r') as f:
            out = json.load(f)
            return out

    offset = 0
    out = []
    for i in range(MAX_QUERIES):
        num_tx = len(out)
        progress.report(num_tx, "Retrieving transaction {} of {} ...".format(num_tx + 1, progress.num_txs))

        data = FcdAPI.get_txs(wallet_address, offset)
        result = data["txs"]
        out.extend(result)

        if len(result) == LIMIT_FCD and "next" in data:
            offset = data["next"]
        else:
            break

    message = "Retrieved total {} txids...".format(len(out))
    progress.report_message(message)

    # Debugging only: when --debug flat set, write to cache file
    if localconfig.debug:
        with open(DEBUG_FILE, 'w') as f:
            json.dump(out, f, indent=4)
        logging.info("Wrote to %s for debugging", DEBUG_FILE)

    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()