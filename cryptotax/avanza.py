from collections import defaultdict
from typing import Dict, Tuple, List, Any
from copy import deepcopy
from datetime import datetime, timedelta

from tabulate import tabulate
import pandas as pd
import pydash
import matplotlib.pyplot as plt

from .load_data import _load_csv


# FIXME: Handle assets priced in USD/EUR correctly


_typ_to_type = {
    "Insättning": "deposit",
    "Uttag": "withdrawal",
    "Köp": "buy",
    "Köp, rättelse": "buy",
    "Sälj": "sell",
    "Sälj, rättelse": "sell",
    "Räntor": "interest",
    "Överföring från Nordea": "buy",
    "Övf fr Nordea": "buy",
    "Utdelning": "dividend",
}


isin_registry = {}

isin_to_avanza_ids = {
    "SE0007126024": 563966,  # Bitcoin
    "SE0010296574": 791709,  # Ethereum
    "NO0010582984": 463161,  # DNB Global
    "LU0099574567": 379,     # Fidelity Global Technology
    "SE0000709123": 1933,    # Swedbank Robur Ny Teknik
    "SE0009779705": 788394,  # Avanza Auto 6
    "SE0008613939": 693994,  # Spiltan Globalfond Investmentbolag
    "SE0004297927": 325406,  # Spiltan Aktiefond Investmentbolag
    "SE0011527613": 878733,  # Avanza Global
    "US0079031078": 529720,  # AMD
}


def _load_data_avanza(filename="./data_private/avanza-transactions_utf8.csv") -> List[Dict]:
    data = _load_csv(filename, delimiter=";")
    for row in data:
        row["date"] = row.pop("Datum")
        ttype = row.pop("Typ av transaktion")
        if ttype in _typ_to_type:
            row["type"] = _typ_to_type[ttype]
        else:
            # print(type)
            row["type"] = ttype

        row["asset_name"] = row.pop("Värdepapper/beskrivning")
        row["asset_id"] = row.pop('ISIN')
        isin_registry[row["asset_id"]] = row["asset_name"]

        volume = row.pop("Antal")
        row["volume"] = abs(float(volume.replace(",", "."))) if volume != "-" else None

        price = row.pop("Kurs")
        row["price"] = float(price.replace(",", ".")) if price != "-" else None

        amount = row.pop("Belopp")
        row["amount"] = float(amount.replace(",", ".")) if amount != "-" else None

        row['currency'] = row.pop("Valuta")

        row.pop("Konto")
        row.pop("Courtage")

    for tx in data:
        if tx['type'] == "MERGER MED TESLA 1 PÅ 0,11":
            tx['type'] = 'sell'
            tx['price'] = 20.75
            tx['amount'] = tx['price'] * tx['volume']
        elif tx['type'] == "MERGER MED SOLARCITY 0,11 PÅ 1":
            tx['type'] = 'buy'
            tx['price'] = 20.75 / 0.11
            tx['amount'] = tx['price'] * tx['volume']

    #print(data[0].keys())
    return data


def compute_balances(trades) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
    balances: Dict[str, float] = defaultdict(lambda: 0)
    costavg: Dict[str, float] = defaultdict(lambda: 0)
    profit: Dict[str, float] = defaultdict(lambda: 0)

    for t in sorted(trades, key=lambda t: t['date']):
        if t["type"] == "buy":
            prev_cost = balances[t['asset_id']] * costavg[t['asset_id']]
            balances[t['asset_id']] += t['volume']
            if balances[t['asset_id']] == 0:
                print(f"new balance was zero, something is wrong: \n - {t}\n - {t['volume']}\n - {balances[t['asset_id']]}")
            elif t['price']:
                new_cost = t['volume'] * t['price']
                costavg[t['asset_id']] = (prev_cost + new_cost) / balances[t['asset_id']]
            else:
                # Special case where stock was transfered without price attached
                pass
        elif t["type"] == "dividend":
            profit[t["asset_id"]] += t["amount"]
        elif t["type"] == "sell":
            #print(costavg[t['asset']])
            p = (t["price"] - costavg[t["asset_id"]]) * t["volume"]
            profit[t["asset_id"]] += p
            #print(f"Profited: {p}")
            balances[t['asset_id']] -= t['volume']
    return balances, costavg, profit


def plot_holdings(txs: List[Dict]) -> None:
    for group, group_txs in pydash.group_by(txs, lambda tx: tx["asset_id"]).items():
        group_txs = [tx for tx in group_txs if tx["volume"] and tx["type"] in ["buy", "sell"]]
        if not group_txs:
            continue
        df = asset_txs_to_dataframe(group_txs)

        if 1000 <= round(df.iloc[-1]['purchase_cost']) <= 300000:
            plt.plot(df['holdings'], label=group_txs[0]['asset_name'])
            # print(df)

    plt.title("Value of holdings")
    plt.ylabel("SEK")
    plt.xlim(pd.Timestamp("2017-01-01"), pd.Timestamp.now())
    plt.legend()
    plt.show()


def txs_to_dataframe(txs: List[Dict]) -> pd.DataFrame:
    index = [pd.Timestamp(tx['date']) for tx in txs]
    txs = deepcopy(txs)
    for tx in txs:
        tx.pop('date')
        tx['volume'] *= 1 if tx['type'] == "buy" else -1
    df = pd.DataFrame(txs, index=index)
    df.sort_index(inplace=True)
    return df


def _calc_costavg(df: pd.DataFrame) -> pd.DataFrame:
    df['costavg'] = df['price']
    df['balance'] = df['volume']
    for i, d in list(enumerate(df.index))[1:]:
        df.iloc[i, df.columns.get_loc('balance')] += df.iloc[i - 1]['balance']

        prev_cost = df.iloc[i - 1]['balance'] * df.iloc[i - 1]['costavg']
        if df.iloc[i]['type'] == "buy":
            new_cost = df.iloc[i]['price'] * df.iloc[i]['volume']
            df.iloc[i, df.columns.get_loc('costavg')] = (prev_cost + new_cost) / df.iloc[i]['balance']
        else:
            df.iloc[i, df.columns.get_loc('costavg')] = df.iloc[i - 1]['costavg']

        df.iloc[i, df.columns.get_loc('profit')] = df.iloc[i - 1]['profit']
        if df.iloc[i]['type'] == "sell":
            df.iloc[i, df.columns.get_loc('profit')] += -df.iloc[i]['volume'] * (df.iloc[i]['price'] - df.iloc[i]['costavg'])
    return df


def _fill_with_daily_prices(df: pd.DataFrame) -> pd.DataFrame:
    from .avanza_api import get_history
    isin = df.iloc[0]['asset_id']
    if isin in isin_to_avanza_ids:
        pricehistory = dict((str(dt.date()), p) for dt, p in get_history(isin_to_avanza_ids[isin]))
    else:
        print(f"Could not get price history for {df.iloc[0]['asset_name']} ({isin})")
        return df

    def _create_row(r, dt):
        dtstr = dt.isoformat()[:10]
        if dtstr not in pricehistory:
            return None
        return {
            "asset_name": r["asset_name"],
            "asset_id": r["asset_id"],
            "date": dt,
            "price": pricehistory[dtstr],
            "balance": r["balance"],
            "costavg": r["costavg"],
            "profit": r["profit"],
            "volume": 0,
        }
    rows = []
    for r1, r2 in [(df.iloc[i], df.iloc[i + 1]) for i in range(len(df) - 1)]:
        start = r1.name
        end = r2.name
        dt = start
        while dt + timedelta(days=1) < end:
            dt += timedelta(days=1)
            row = _create_row(r1, dt)
            if row:
                rows.append(row)
    if not rows:
        return df
    now = datetime.now()
    dt = end
    while dt + timedelta(days=1) < now:
        dt += timedelta(days=1)
        row = _create_row(r2, dt)
        if row:
            rows.append(row)
    df = df.append(pd.DataFrame(rows).set_index("date"), sort=False).sort_index()
    return df


def test_fill_with_daily_prices() -> None:
    txs = [
        {"date": pd.Timestamp("2018-09-01"), "asset_id": "SE0011527613", "asset_name": "Avanza Global", "type": "buy", "price": 1, "volume": 1},
        {"date": pd.Timestamp("2018-09-25"), "asset_id": "SE0011527613", "asset_name": "Avanza Global", "type": "sell", "price": 2, "volume": 1},
    ]
    df = asset_txs_to_dataframe(txs)
    assert df.loc["2018-09-03"]["price"]


def asset_txs_to_dataframe(txs: List[Dict]) -> pd.DataFrame:
    assert all(tx['asset_id'] == txs[0]['asset_id'] for tx in txs)
    currency_factor_to_sek = 9 if "US" in txs[0]["asset_id"] else 1
    df = txs_to_dataframe(txs)
    df['profit'] = 0.0
    df = _calc_costavg(df)
    df = _fill_with_daily_prices(df)

    df['balance'] = df['balance'].round(2)
    df['holdings'] = (df['balance'] * df['price']).round(2) * currency_factor_to_sek
    df['purchase_cost'] = (df['balance'] * df['costavg']).round(2) * currency_factor_to_sek
    df['profit_unrealized'] = df['holdings'] - df['purchase_cost']
    return df


def print_overview(txs) -> None:
    balances, costavg, profit = compute_balances(txs)
    rows: List[Any] = []
    for k in sorted(balances.keys(), key=lambda k: -balances[k] * costavg[k]):
        #if round(balances[k], 6) != 0:
            purchase_cost = round(balances[k] * costavg[k])
            rows.append([isin_registry[k], k, round(balances[k], 6), costavg[k], profit[k], purchase_cost])

    print(tabulate(rows, headers=["name", "id", "balance", "costavg", "profit", "purchase_cost"]))


def print_unaccounted_txs(txs):
    print("Unaccounted txs:")
    for tx in txs:
        if tx['type'] not in ["buy", "sell", "deposit", "withdrawal", "dividend", "interest"]:
            print(tx)
        if tx['currency'] != "SEK":
            print(tx)


def print_overview_df(txs: List[Dict]) -> None:
    last_entries = []
    for group, group_txs in pydash.group_by(txs, lambda tx: tx["asset_id"]).items():
        group_txs = [tx for tx in group_txs if tx["volume"] and tx["type"] in ["buy", "sell"]]
        if not group_txs:
            continue
        df = asset_txs_to_dataframe(group_txs)
        last_entries.append(df.iloc[-1])
    for entry in last_entries:
        del entry["amount"]
        del entry["type"]
        del entry["volume"]
        del entry["currency"]
    df = pd.DataFrame(last_entries)
    print(df)


if __name__ == "__main__":
    txs = _load_data_avanza()
    # print_overview(txs)
    print_overview_df(txs)
    # print_unaccounted_txs(txs)
    plot_holdings(txs)
