import py_vollib.black_scholes_merton.implied_volatility as BSMiv
import py_vollib.black_scholes_merton.greeks.analytical as BSMgreeks
import numpy as np
import pandas as pd
import datetime as dt
import json

# Read expire_date.json and create a dictionary with underlying_instr_id as key and expiredate as value
with open("expire_date.json", "r", encoding="utf-8") as f:
    expiredate = json.load(f)

# Read trade_para.json and create a dictionary with product as key and the rest of the columns as a dict
with open("trade_para.json", "r", encoding="utf-8") as f:
    trade_para = json.load(f)

# Read tradingDay.json and create an array of trading_day as strings for fast lookup
with open("tradingDay.json", "r", encoding="utf-8") as f:
    trading_days_list = json.load(f)
tradingDay = np.array(trading_days_list)


def findInsInfo(future_id):
    # Extract product_id: all leading letters before the first digit
    import re

    match = re.match(r"^([A-Za-z]+)", future_id)
    if not match:
        raise ValueError(f"Invalid future_id '{future_id}': cannot extract product id.")
    product_id = match.group(1).upper()
    if product_id not in trade_para:
        raise ValueError(f"Product id '{product_id}' not found in trade_para.")
    if future_id not in expiredate:
        raise ValueError(f"Future id '{future_id}' not found in expiredate.")
    product_info = trade_para[product_id]
    expiredate_info = expiredate[future_id]
    product_info["expiredate"] = expiredate_info
    return product_info


def split_instrument(instrument):
    """
    Splits an instrument string into its components:
    - product: e.g. 'TA'
    - underlying_id: e.g. 'TA501'
    - type: 'C' or 'P'
    - strike: int, e.g. 1600

    Handles formats like 'TA501C1600' or 'TA501-C-1600'.
    Raises ValueError if not in the expected pattern.
    """
    import re

    # Remove any dashes for easier parsing
    s = instrument.replace("-", "")

    # Regex: product (letters), yymm (digits), type (C/P), strike (digits)
    m = re.match(r"([A-Z]+)(\d{3,4})([CP])(\d+)", s, re.I)
    if not m:
        raise ValueError(
            f"Instrument '{instrument}' does not match expected pattern like 'TA501C1600' or 'TA501-C-1600'."
        )

    product = m.group(1).upper()
    yymm = m.group(2)
    typ = m.group(3).lower()
    strike = int(m.group(4))
    underlying_id = f"{m.group(1)}{yymm}"

    return {
        "product": product,
        "underlying_id": underlying_id,
        "type": typ,
        "strike": strike,
    }


def findPortfolioDetails(future_id, portfolio, s, ttm, iv, cost=0, iv_map=None):
    t = ttm / 365
    info = findInsInfo(future_id)
    multiple = info["volume_multiple"]
    margin_ratio = info["margin_ratio"]
    commission = info["open_money_by_vol"]
    portfolio_price = 0
    delta = 0
    gamma = 0
    vega = 0
    theta = 0
    margin = 0
    portfolio_price_afterfee = 0
    for opt_code in portfolio:
        opt_info = split_instrument(opt_code)
        k = opt_info["strike"]
        typ = opt_info["type"]
        thisfuture_id = opt_info["underlying_id"]
        if thisfuture_id != future_id:
            raise ValueError(
                f"Option '{opt_code}' has different underlying_id '{thisfuture_id}' from future_id '{future_id}'."
            )
        num_hold = portfolio[opt_code]
        opt_iv = iv_map.get(opt_code, iv) if iv_map else iv
        # print(typ, s, k, t, 0, opt_iv, 0)
        optprice = (
            BSMiv.black_scholes_merton(typ, s, k, t, 0, opt_iv, 0) * multiple * num_hold
        )
        portfolio_price += optprice
        delta += BSMgreeks.delta(typ, s, k, t, 0, opt_iv, 0) * multiple * num_hold
        gamma += BSMgreeks.gamma(typ, s, k, t, 0, opt_iv, 0) * multiple * num_hold
        vega += BSMgreeks.vega(typ, s, k, t, 0, opt_iv, 0) * multiple * num_hold
        theta += BSMgreeks.theta(typ, s, k, t, 0, opt_iv, 0) * multiple * num_hold
        if num_hold < 0:
            margin -= s * num_hold * margin_ratio * multiple / 2 + optprice
        portfolio_price_afterfee += optprice - commission * abs(num_hold)
    pnl = portfolio_price - cost
    pnl_afterfee = portfolio_price_afterfee - cost
    return [
        portfolio_price,
        delta,
        gamma,
        vega,
        theta,
        margin,
        portfolio_price_afterfee,
        pnl,
        pnl_afterfee,
    ]


def findPairScenrio(future_id, portfolio, iv, cost=0, iv_map=None):
    optinfo = findInsInfo(future_id)
    today = dt.date.today().strftime(format="%Y%m%d")
    # Filter trading days: >= today and <= expiredate
    expire_date = optinfo["expiredate"]
    date_lst = [d for d in tradingDay if today <= d <= expire_date]
    multi = optinfo["volume_multiple"]
    tick = optinfo["price_tick"]
    commission = optinfo["open_money_by_vol"]
    exchange = optinfo["exchange_id"]
    margin_ratio = optinfo["margin_ratio"] / 2

    # find largest k and lowest k
    all_strikes = []
    for opt_code in portfolio:
        opt_info = split_instrument(opt_code)
        all_strikes.append(opt_info["strike"])
    maxs = max(all_strikes) * 1.2
    lows = min(all_strikes) * 0.8
    index = np.round(np.linspace(lows, maxs, 30), 1)
    columns = date_lst
    keys = [
        "portfolio_price",
        "delta",
        "gamma",
        "vega",
        "theta",
        "margin",
        "LotsDelta",
        "portfolio_price_afterfee",
        "pnl",
        "pnl_afterfee",
    ]
    dataframe_dict = {}
    for key in keys:
        df = pd.DataFrame(0.0, index=index, columns=columns, dtype=float)
        dataframe_dict[key] = df
    for s in index:
        for date in columns:
            # Calculate ttm as the difference in days between date and expire_date, both in 'YYYYMMDD' string format
            ttm = (
                pd.to_datetime(expire_date, format="%Y%m%d")
                - pd.to_datetime(date, format="%Y%m%d")
            ).days + 1
            (
                portfolio_price,
                delta,
                gamma,
                vega,
                theta,
                margin,
                portfolio_price_afterfee,
                pnl,
                pnl_afterfee,
            ) = findPortfolioDetails(future_id, portfolio, s, ttm, iv, cost, iv_map=iv_map)
            dataframe_dict["portfolio_price"].loc[s, date] = portfolio_price
            dataframe_dict["delta"].loc[s, date] = delta
            dataframe_dict["gamma"].loc[s, date] = gamma
            dataframe_dict["vega"].loc[s, date] = vega
            dataframe_dict["theta"].loc[s, date] = theta
            dataframe_dict["margin"].loc[s, date] = margin
            dataframe_dict["portfolio_price_afterfee"].loc[
                s, date
            ] = portfolio_price_afterfee
            dataframe_dict["pnl"].loc[s, date] = pnl
            dataframe_dict["pnl_afterfee"].loc[s, date] = pnl_afterfee

    dataframe_dict["LotsDelta"] = dataframe_dict["delta"] / multi
    for key in dataframe_dict:
        decimals = 4 if key == "gamma" else 2
        dataframe_dict[key] = np.round(dataframe_dict[key], decimals)
    s = index[0]
    # date = columns[0]
    # ttm = (
    #     pd.to_datetime(expire_date, format="%Y%m%d")
    #     - pd.to_datetime(date, format="%Y%m%d")
    # ).days + 1
    # (
    #     portfolio_price,
    #     delta,
    #     gamma,
    #     vega,
    #     theta,
    #     margin,
    #     portfolio_price_afterfee,
    #     pnl,
    #     pnl_afterfee,
    # ) = findPortfolioDetails(future_id, portfolio, s, ttm, iv, cost)
    # print(portfolio_price, delta, gamma, vega, theta, margin)
    return dataframe_dict


# print(findPairScenrio("TA601", {"TA601C1600": 1, "TA601P1800": -1}, 0.2))
