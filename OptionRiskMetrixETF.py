import pandas as pd
import numpy as np
import commodity_common_functions as CCF
import seaborn as sns
import dataframe_image as dfi
from pathlib import Path
import json
import datetime as dt
from datetime import datetime
import akshare as ak

retMap = {}


def findRetDistribution(product_id, t):
    if product_id in retMap:
        info = retMap[product_id]
    else:
        info = ak.fund_etf_hist_em(
            symbol=product_id,
            period="daily",
            start_date="20000101",
            end_date="20500101",
            adjust="hfq",
        )[["日期", "收盘"]]
        info.columns = ["date", "close"]
        info["dailyRet_main"] = info["close"].pct_change()
        info["cumulative_prod"] = (info["dailyRet_main"] + 1).cumprod()
        info["date"] = info["date"].apply(lambda x: x[:4] + x[5:7] + x[8:10])
        info.index = info["date"]
        retMap[product_id] = info
    rolling_product = info["cumulative_prod"] / info["cumulative_prod"].shift(t).fillna(
        1
    )
    return rolling_product


close_dict = {}


def findETFclose(date, code):
    if code in close_dict:
        temp = close_dict[code]
    else:
        temp = ak.fund_etf_hist_em(symbol=code, period="daily")
        temp["日期"] = temp["日期"].apply(lambda x: x[:4] + x[5:7] + x[8:])
        close_dict[code] = temp
    # print(ak.fund_etf_hi'st_em(symbol=code, period="daily", end_date=date))
    return float(temp[temp["日期"] <= date].iloc[-1]["收盘"])


def findOptionPrice(date):
    SQL_cmd = f"""SELECT instrument_id, trading_date, close, volume, underlying_instr_id
    FROM daily_data_ut
    WHERE trading_date = '{date}'
    """
    df = pd.read_sql(sql=SQL_cmd, con=CCF.std_market_data)
    df_merged = df[df["instrument_id"].str.len() > 6]
    df_merged = df_merged.rename(columns={"close": "option_close"})
    SQL_cmd = f"""
    SELECT instrument_id, strike_price as strike, options_type as opt_typ, exchange_id, expiredate, volume_multiple as multiplier, price_tick
    FROM instrument
    WHERE instrument_id IN {tuple(df_merged['instrument_id'])}
    """
    info = pd.read_sql(sql=SQL_cmd, con=CCF.market_base)
    info["sector"] = "ETF"
    info["commission"] = 1.7 / 2
    info["updownlimit"] = 0.1
    df = pd.merge(df_merged, info, on="instrument_id", how="left")
    invalid_rows = []
    error_set = []
    for index, row in df.iterrows():
        try:
            type_ = "c" if row["opt_typ"] == "1" else "p"
            k = row["strike"]
            underlying_id = row["underlying_instr_id"]
            und_close = findETFclose(date, underlying_id)
            df.at[index, "underlying_close"] = und_close
            df.at[index, "opt_typ"] = type_
            if (type_ == "c" and und_close > k) or (type_ == "p" and und_close < k):
                invalid_rows.append(index)
                continue
            expiredate = row["expiredate"]
            ttm = len(
                CCF.tradingDay[(CCF.tradingDay > date) & (CCF.tradingDay <= expiredate)]
            )
            df.at[index, "tdtm"] = ttm
            df.at[index, "cdtm"] = (
                datetime.strptime(expiredate, "%Y%m%d")
                - datetime.strptime(date, "%Y%m%d")
            ).days
            exchange = "SZ" if row["exchange_id"] == "SZSE" else "SH"
            df.at[index, "windcode"] = row["instrument_id"] + "." + exchange
            if underlying_id == "510300":
                con_undcode = "沪深300"
            elif underlying_id == "510500":
                con_undcode = "中证500"
            elif underlying_id == "510050":
                con_undcode = "上证50"
            elif underlying_id == "159915":
                con_undcode = "创业板"
            elif underlying_id == "588000":
                con_undcode = "科创50"
            elif underlying_id == "159901":
                con_undcode = "深证100"
            conepire = expiredate[2:6]
            df.at[index, "ezCode"] = f"{con_undcode}_{conepire}_{k}{type_}"
            iv = CCF.IV(row["option_close"], und_close, k, ttm / 243, 0, type_)
            df.at[index, "iv"] = iv
            df.at[index, "delta"] = CCF.BSMgreeks.delta(
                type_, und_close, k, ttm / 243, 0, iv, 0
            )
            otmvalue = und_close - k if type_ == "p" else k - und_close
            multi = row["multiplier"]
            otmvalue = max(otmvalue, 0)
            # 计算保证金
            if type_ == "c":  # 看涨期权
                margin_rate_1 = 0.12 * und_close - otmvalue
                margin_rate_2 = 0.07 * und_close
                margin = (
                    row["option_close"] + max(margin_rate_1, margin_rate_2)
                ) * multi
            else:  # 看跌期权
                margin_rate_1 = 0.12 * und_close - otmvalue
                margin_rate_2 = 0.07 * k
                margin = (
                    min(row["option_close"] + max(margin_rate_1, margin_rate_2), k)
                    * multi
                )
            # orimargin = row["underlying_close"] * multi * 0.12
            df.at[index, "margin"] = margin
        except:
            # 若解析失败，记录行索引
            #             print(row['instrument_id'], ValueError)
            invalid_rows.append(index)
            error_set.append((index, row["instrument_id"], ValueError))
    df = df.drop(invalid_rows).dropna().reset_index(drop=True)
    df[["volume", "tdtm", "cdtm", "multiplier"]] = df[
        ["volume", "tdtm", "cdtm", "multiplier"]
    ].astype(int)
    return df


def getPayoffSeries(product, dtm, underlying_close, strike, opt_typ):
    pricedis = findRetDistribution(product, dtm) * underlying_close
    if opt_typ == "c":
        payoffser = pricedis - strike
    else:
        payoffser = strike - pricedis
    payoffser[payoffser < 0] = 0
    return payoffser


def ETF_Option_Raw_Data(wind_code: str, tradingdate: str):
    """

    :param wind_code:
    :param tradingdate:
    :return: dataframe 包含字段 id, seq_no, Bid1, Ask1, MidPrice
    """
    future_path = CCF.Ftp_Path(tradingdate)
    option_data = f"{future_path}ut_std_data/{tradingdate}/{wind_code}.csv"
    # print(option_data)
    OptionData = pd.read_csv(
        option_data,
        usecols=["id", "seq_no", "bid_price1", "ask_price1"],
        dtype={
            "id": object,
            "seq_no": np.int64,
            "bid_price1": np.float64,
            "ask_price1": np.float64,
        },
        escapechar="/",
        na_values=r"\N",
    )

    OptionData.rename(
        columns={"bid_price1": "Bid1", "ask_price1": "Ask1"}, inplace=True
    )
    OptionData.loc[:, "MidPrice"] = 0.5 * (OptionData["Bid1"] + OptionData["Ask1"])

    return OptionData


if __name__ == "__main__":
    date = (dt.date.today()).strftime(format="%Y%m%d")
    date = "20250418"
    # 读取期权价格数据
    optdf = findOptionPrice(date)
    # 设置期权价格数据的索引
    optdf.index = optdf["ezCode"]
    # 调整保证金
    optdf["margin"] = optdf["margin"] * 1.1
    optdf["margin"] = optdf["margin"].round(0)
    # 计算期权的收益
    payoffmap = {}

    def calculate_payoff(row):
        ins_id = row["instrument_id"]
        product = row["underlying_instr_id"]
        dtm = row["tdtm"]
        underlying_close = row["underlying_close"]
        strike = row["strike"]
        opt_typ = row["opt_typ"]
        payoff = (
            getPayoffSeries(product, dtm, underlying_close, strike, opt_typ)
            * row["multiplier"]
        )
        payoffmap[ins_id] = payoff
        return pd.Series(
            [payoff.mean(), payoff.quantile(0.95), payoff.max(), len(payoff)]
        )

    optdf["NumLimit"] = (
        np.abs(np.log(optdf["strike"] / optdf["underlying_close"]))
        / optdf["updownlimit"]
    ).round(2)
    optdf["TradingValue"] = (
        optdf["option_close"] * optdf["multiplier"] * optdf["volume"]
    )
    optdf[["ExpectedPayoff", "Q95Payoff", "MaxPayoff", "DaysInSample"]] = optdf.apply(
        calculate_payoff, axis=1
    )
    # 计算期权的信用收取
    optdf["CreditCollected"] = optdf["option_close"] * optdf["multiplier"]
    # 计算期权的预期承保费
    optdf["ExpectedLotPremium"] = optdf["CreditCollected"] - optdf["ExpectedPayoff"]
    # 计算期权的理想收益
    optdf["IdealRet(C)"] = (
        (optdf["CreditCollected"] - optdf["commission"])
        / optdf["margin"]
        * 365
        / optdf["cdtm"]
    )
    # 计算期权的预期边际收益
    optdf["EMarginRet(C)"] = (
        (optdf["ExpectedLotPremium"] - optdf["commission"] * 2)
        / optdf["margin"]
        * 365
        / optdf["cdtm"]
    )
    # 计算期权的95%边际收益
    optdf["95MarginRet(C)"] = (
        (
            optdf["option_close"] * optdf["multiplier"]
            - optdf["Q95Payoff"]
            - optdf["commission"] * 2
        )
        / optdf["margin"]
        * 365
        / optdf["cdtm"]
    )
    # 计算期权的最差边际收益
    optdf["WorstMarginRet(C)"] = (
        (
            optdf["option_close"] * optdf["multiplier"]
            - optdf["MaxPayoff"]
            - optdf["commission"] * 2
        )
        / optdf["margin"]
        * 365
        / optdf["cdtm"]
    )

    optdf["IdealRet(T)"] = (
        (optdf["CreditCollected"] - optdf["commission"])
        / optdf["margin"]
        * 243
        / optdf["tdtm"]
    )
    # 计算期权的预期边际收益
    optdf["EMarginRet(T)"] = (
        (optdf["ExpectedLotPremium"] - optdf["commission"] * 2)
        / optdf["margin"]
        * 243
        / optdf["tdtm"]
    )
    # 计算期权的95%边际收益
    optdf["95MarginRet(T)"] = (
        (
            optdf["option_close"] * optdf["multiplier"]
            - optdf["Q95Payoff"]
            - optdf["commission"] * 2
        )
        / optdf["margin"]
        * 243
        / optdf["tdtm"]
    )
    # 计算期权的最差边际收益
    optdf["WorstMarginRet(T)"] = (
        (
            optdf["option_close"] * optdf["multiplier"]
            - optdf["MaxPayoff"]
            - optdf["commission"] * 2
        )
        / optdf["margin"]
        * 243
        / optdf["tdtm"]
    )

    optdf = optdf.dropna()

    # 复制一份期权数据，为筛选后结果
    std_df = optdf.copy()
    # 筛选出预期边际收益大于等于0.05的数据
    std_df = std_df[std_df["EMarginRet(C)"] >= 0.05]
    # 筛选出delta绝对值小于0.1的数据
    std_df = std_df[np.abs(std_df["delta"]) < 0.1]
    # 筛选出dtm小于等于20的数据
    std_df = std_df[std_df["tdtm"] <= 35]
    # 筛选出持仓量大于等于200的数据
    std_df = std_df[std_df["volume"] >= 500]
    # 筛选出最大收益为0且样本天数大于等于500的数据
    std_df = std_df[(std_df["MaxPayoff"] == 0) & (std_df["DaysInSample"] >= 500)]

    #  输入为一行optdf，输出该行在该交易日14:55时间点的ask和bid
    def findOptionQuote(row):
        date = row["trading_date"]
        ins = row["instrument_id"]
        try:
            row = ETF_Option_Raw_Data(ins, date).iloc[-601]
            return float(row["Ask1"]), float(row["Bid1"])
        except:
            return np.nan, np.nan

    std_df["bid"] = std_df.apply(lambda x: findOptionQuote(x)[1], axis=1)
    # std_df.to_csv('./tets.csv')
    # 生成excel数据
    exceldf = std_df[
        [
            "instrument_id",
            "underlying_instr_id",
            "option_close",
            "sector",
            "NumLimit",
            "EMarginRet(C)",
            "EMarginRet(T)",
            "margin",
            "tdtm",
            "cdtm",
            "bid",
        ]
    ].dropna()
    exceldf = exceldf[exceldf["bid"] > 0].reset_index()
    exceldf["EMarginRet(C)"] = (exceldf["EMarginRet(C)"] * 100).round(2)
    exceldf["EMarginRet(T)"] = (exceldf["EMarginRet(T)"] * 100).round(2)
    undrownum = exceldf.groupby("underlying_instr_id").size()
    undmeanret = (
        exceldf.groupby("underlying_instr_id")["EMarginRet(T)"]
        .mean()
        .sort_values(ascending=False)
    )
    exceldf = exceldf.groupby(["underlying_instr_id", "instrument_id"]).first()
    result = []
    cnt = 0
    sett = []
    for und in undmeanret.index:
        thisnum = undrownum[und]
        if thisnum + cnt > 120:
            result.append(exceldf.loc[(sett, slice(None)), :])
            sett = [und]
            cnt = thisnum
        else:
            sett.append(und)
            cnt += thisnum
    result.append(exceldf.loc[(sett, slice(None)), :])

    # 生成json数据
    jsondf = std_df.reset_index(drop=True)
    jsonoutput = []
    for ind, row in jsondf.iterrows():
        rowjs = {}
        idd = f"{date[2:]}#{ind + 1}"
        rowjs["_id"] = idd
        rowjs["idnum"] = ind + 1
        rowjs["create_date"] = date
        rowjs["underlying_id"] = row["underlying_instr_id"]
        rowjs["sector"] = row["sector"]
        rowjs["margin_req"] = row["margin"]
        rowjs["expire_date"] = row["expiredate"]
        rowjs["STG_TYP"] = ["NK_SELL"]
        rowjs["HEDG_MTD"] = ["StopLoss"]
        rowjs["option_structure"] = {row["instrument_id"]: -1}
        rowjs["risk_params"] = {
            "limit_price": row["option_close"] * -1,
            "ExpectedPayoff": row["ExpectedPayoff"],
            "EMarginRet": row["EMarginRet(T)"],
        }
        jsonoutput.append(rowjs)

    # 保存json数据
    direc = f"E:\\KurStrategyETF\\dailySummary\\{date}\\"
    Path(direc).mkdir(parents=True, exist_ok=True)
    with open(direc + f"{date}_jssave.json", "w") as f:
        json.dump(jsonoutput, f)
    # 保存excel数据
    optdf.to_excel(direc + f"{date}_totalSet.xlsx")
    std_df.to_excel(direc + f"{date}_selectSet.xlsx")
    # 生成excel图片
    direc = f"E:\\KurStrategyETF\\dailySummary\\{date}\\picfile\\"
    Path(direc).mkdir(parents=True, exist_ok=True)
    for i in range(len(result)):
        dfi.export(
            result[i],
            f"{direc}{date}_selectSetSimp_{i+1}.png",
            fontsize=2,
            dpi=900,
            table_conversion="chrome",
            chrome_path="C:\Program Files\Google\Chrome Dev\Application\chrome.exe",
            max_rows=-1,
        )
