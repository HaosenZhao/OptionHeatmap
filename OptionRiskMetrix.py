import numpy as np
import pandas as pd
import commodity_common_functions as CCF
import seaborn as sns
import dataframe_image as dfi
from pathlib import Path
import json
import datetime as dt
from datetime import datetime

##### 注： shares delta for IC IM need to updated


retMap = {}


def findRetDistribution(product_id, t):
    if product_id in retMap:
        info = retMap[product_id]
    else:
        SQL_cmd = f"""SELECT TRADE_DATE, PRODUCT_ID, dailyRet_main
            FROM RY_FULL
            WHERE PRODUCT_ID = '{product_id}'
            """
        info = (
            pd.read_sql(sql=SQL_cmd, con=CCF.research)
            .drop_duplicates(subset="TRADE_DATE", keep="first")
            .sort_values("TRADE_DATE")
            .dropna()
        )
        info["cumulative_prod"] = (info["dailyRet_main"] + 1).cumprod()
        info.index = info["TRADE_DATE"]
        retMap[product_id] = info
    rolling_product = info["cumulative_prod"] / info["cumulative_prod"].shift(t).fillna(
        1
    )
    return rolling_product


#### 全量信息，输入为日期，输出为全量信息
def findOptionPrice(date):
    SQL_cmd = f"""SELECT instrument_id, trading_date, close, volume, open_interest,underlying_instr_id
    FROM daily_data_option
    WHERE trading_date = '{date}'
    """
    df = pd.read_sql(sql=SQL_cmd, con=CCF.std_market_data)
    df["underlying_instr_id"] = df["underlying_instr_id"].apply(
        lambda x: (
            "IH" + x[2:]
            if x.startswith("HO")
            else (
                "IF" + x[2:]
                if x.startswith("IO")
                else ("IM" + x[2:] if x.startswith("MO") else x)
            )
        )
    )

    datebar = date[:4] + "-" + date[4:6] + "-" + date[6:]
    SQL_cmd = f"""SELECT instrument_id, trading_date, close
    FROM daily_data
    WHERE trading_date = '{datebar}'
    """
    unddf = pd.read_sql(sql=SQL_cmd, con=CCF.std_market_data)
    unddf["trading_date"] = unddf["trading_date"].apply(
        lambda x: x[:4] + x[5:7] + x[8:10]
    )

    df = pd.merge(
        df,
        unddf,
        left_on=["underlying_instr_id", "trading_date"],
        right_on=["instrument_id", "trading_date"],
        how="left",
    )
    df = df.rename(columns={"close_y": "underlying_close", "close_x": "option_close"})
    df = df.drop(columns=["instrument_id_y"])
    df = df.rename(columns={"instrument_id_x": "instrument_id"})

    info_dict = findUnderlyingOptionInfo(date)

    invalid_rows = []
    error_set = []
    # 遍历每一行
    for index, row in df.iterrows():
        try:
            prod, underlying_id, type_, k = parse_option_contract(row["instrument_id"])
            if (type_ == "c" and row["underlying_close"] > k) or (
                type_ == "p" and row["underlying_close"] < k
            ):
                invalid_rows.append(index)
                continue
            expiredate = info_dict[underlying_id]["expiredate"]
            exchange = info_dict[underlying_id]["exchange_id"]
            commission = info_dict[underlying_id]["open_money_by_vol"]
            margin_ratio = info_dict[underlying_id]["margin_ratio"]
            multi = info_dict[underlying_id]["volume_multiple"]
            tick = info_dict[underlying_id]["price_tick"]
            sector = info_dict[underlying_id]["sector"]
            updownlimit = info_dict[underlying_id]["updownlimit"]

            ttm = len(
                CCF.tradingDay[(CCF.tradingDay > date) & (CCF.tradingDay <= expiredate)]
            )
            df.at[index, "product"] = prod
            df.at[index, "sector"] = sector
            df.at[index, "opt_typ"] = type_
            df.at[index, "strike"] = k
            df.at[index, "tdtm"] = ttm
            df.at[index, "cdtm"] = (
                datetime.strptime(expiredate, "%Y%m%d")
                - datetime.strptime(date, "%Y%m%d")
            ).days
            df.at[index, "commission"] = commission
            df.at[index, "multiplier"] = multi
            df.at[index, "tick"] = tick
            df.at[index, "expiredate"] = expiredate
            df.at[index, "updownlimit"] = updownlimit
            df.at[index, "windcode"] = row["instrument_id"].upper() + "." + exchange
            iv = CCF.IV(
                row["option_close"], row["underlying_close"], k, ttm / 243, 0, type_
            )
            df.at[index, "iv"] = iv
            df.at[index, "delta"] = CCF.BSMgreeks.delta(
                type_, row["underlying_close"], k, ttm / 243, 0, iv, 0
            )
            otmvalue = (
                row["underlying_close"] * multi - k * multi
                if type_ == "p"
                else k * multi - row["underlying_close"] * multi
            )
            otmvalue = max(otmvalue, 0)
            orimargin = row["underlying_close"] * multi * margin_ratio
            df.at[index, "margin"] = row["option_close"] * multi + max(
                orimargin - 0.5 * otmvalue, 0.5 * orimargin
            )
        except:
            # 若解析失败，记录行索引
            #             print(row['instrument_id'], ValueError)
            invalid_rows.append(index)
            error_set.append((index, row["instrument_id"], ValueError))
    df = df.drop(invalid_rows).dropna().reset_index(drop=True)
    df[["volume", "open_interest", "tdtm", "cdtm", "multiplier"]] = df[
        ["volume", "open_interest", "tdtm", "cdtm", "multiplier"]
    ].astype(int)

    return df


def parse_option_contract(contract):
    # 查找第一个数字的位置
    first_digit_index = next(
        (i for i, char in enumerate(contract) if char.isdigit()), None
    )
    if first_digit_index is None:
        raise ValueError(f"无法解析合约: {contract}，未找到数字。")
    product = contract[:first_digit_index]

    if "-" in contract:
        # 处理形如 a2505-C-3850 的合约
        parts = contract.split("-")
        underlying_id = parts[0]
        type_ = parts[1]
        k = float(parts[2])
    else:
        # 处理形如 zn2505P26000 的合约
        type_index = None
        for i in range(1, len(contract) - 1):
            if (
                contract[i].isalpha()
                and contract[i - 1].isdigit()
                and contract[i + 1].isdigit()
            ):
                type_index = i
                break

        if type_index is None:
            raise ValueError(f"无法解析合约: {contract}，请检查合约格式。")

        underlying_id = contract[:type_index]
        type_ = contract[type_index]
        k = float(contract[type_index + 1 :])

    # 修改 underlying_id
    if underlying_id.startswith("HO"):
        underlying_id = "IH" + underlying_id[2:]
        product = "IH"
    elif underlying_id.startswith("IO"):
        underlying_id = "IF" + underlying_id[2:]
        product = "IF"
    elif underlying_id.startswith("MO"):
        underlying_id = "IM" + underlying_id[2:]
        product = "IM"

    return product, underlying_id, type_.lower(), k


def findUnderlyingOptionInfo(date):
    SQL_cmd = f"""
    SELECT underlying_instr_id,instrument_id
    FROM daily_data_option
    WHERE trading_date = '{date}'
    ORDER BY open_interest DESC
    """
    max_open_interest = pd.read_sql(sql=SQL_cmd, con=CCF.std_market_data)
    max_open_interest = (
        max_open_interest.groupby("underlying_instr_id").first().reset_index()
    )
    max_open_interest["underlying_instr_id"] = max_open_interest[
        "underlying_instr_id"
    ].apply(
        lambda x: (
            "IH" + x[2:]
            if x.startswith("HO")
            else (
                "IF" + x[2:]
                if x.startswith("IO")
                else ("IM" + x[2:] if x.startswith("MO") else x)
            )
        )
    )
    SQL_cmd = f"""
    SELECT         
        i.underlying_instr_id,
        i.exchange_id,
        i.expiredate,
        i.volume_multiple,
        i.price_tick,
        icr.open_money_by_vol
    FROM instrument i
    LEFT JOIN commission_info icr ON i.instrument_id = icr.instrument_id
    WHERE i.instrument_id IN {tuple(max_open_interest['instrument_id'])}
    """
    instrument_info = pd.read_sql(sql=SQL_cmd, con=CCF.market_base)
    instrument_info["underlying_instr_id"] = instrument_info[
        "underlying_instr_id"
    ].apply(
        lambda x: (
            "IH" + x[2:]
            if x.startswith("HO")
            else (
                "IF" + x[2:]
                if x.startswith("IO")
                else ("IM" + x[2:] if x.startswith("MO") else x)
            )
        )
    )
    instrument_info["open_money_by_vol"] = np.where(
        instrument_info["underlying_instr_id"].str.startswith(("IH", "IF", "IM")),
        15,
        instrument_info["open_money_by_vol"],
    )
    SQL_cmd = f"""
    SELECT instrument_id as underlying_instr_id, short_margin_ratio as margin_ratio, product_id as product
    FROM instrument
    WHERE instrument_id IN {tuple(max_open_interest['underlying_instr_id'])}
    """
    margin_ratio = pd.read_sql(sql=SQL_cmd, con=CCF.market_base)
    SQL_cmd = f"""
    SELECT PRODUCT_ID as product, WIND_INDUSTRYNAME1 as sector
    FROM WindIndustry_Kurt
    WHERE PRODUCT_ID IN {tuple(margin_ratio['product'])}
    """
    secinfo = pd.read_sql(sql=SQL_cmd, con=CCF.research)
    secinfo.loc[len(secinfo)] = ["IH", "金融"]
    secinfo.loc[len(secinfo)] = ["IF", "金融"]
    secinfo.loc[len(secinfo)] = ["IC", "金融"]
    secinfo.loc[len(secinfo)] = ["IM", "金融"]
    SQL_cmd = f"""
    SELECT         
    instrument_id,
    prev_settlement,
    limit_up
    FROM daily_data
    WHERE trading_date = '{date[:4]}-{date[4:6]}-{date[6:]}'
    """
    limitupdf = pd.read_sql(sql=SQL_cmd, con=CCF.std_market_data)
    limitupdf["updownlimit"] = (
        limitupdf["limit_up"] / limitupdf["prev_settlement"] - 1
    ).round(2)
    limitupdf = limitupdf[["instrument_id", "updownlimit"]]
    limitupdf = limitupdf.rename(columns={"instrument_id": "underlying_instr_id"})

    merged_df = pd.merge(
        max_open_interest, instrument_info, on="underlying_instr_id", how="left"
    )
    merged_df = pd.merge(merged_df, margin_ratio, on="underlying_instr_id", how="left")
    merged_df = pd.merge(merged_df, limitupdf, on="underlying_instr_id", how="left")
    merged_df = pd.merge(merged_df, secinfo, on="product", how="left")
    merged_df = merged_df.drop(columns=["instrument_id"]).dropna()
    merged_dict = merged_df.set_index("underlying_instr_id").T.to_dict("dict")
    for key in merged_dict:
        if merged_dict[key]["exchange_id"] == "CFFEX":
            merged_dict[key]["exchange_id"] = "CFE"
        elif merged_dict[key]["exchange_id"] == "SHFE":
            merged_dict[key]["exchange_id"] = "SHF"
        elif merged_dict[key]["exchange_id"] == "CZCE":
            merged_dict[key]["exchange_id"] = "CZC"
        elif merged_dict[key]["exchange_id"] == "GFEX":
            merged_dict[key]["exchange_id"] = "GFE"
    return merged_dict


def getPayoffSeries(product, dtm, underlying_close, strike, opt_typ):
    pricedis = findRetDistribution(product, dtm) * underlying_close
    if opt_typ == "c":
        payoffser = pricedis - strike
    else:
        payoffser = strike - pricedis
    payoffser[payoffser < 0] = 0
    return payoffser


def longKurtTemp(date):
    optdf = findOptionPrice(date)
    # print(123123)
    # 设置期权价格数据的索引
    optdf.index = optdf["instrument_id"]
    # 计算期权的收益
    payoffmap = {}

    def calculate_payoff(row):
        ins_id = row["instrument_id"]
        product = row["product"]
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
            [
                payoff.mean(),
                payoff.median(),
                payoff.quantile(0.9),
                payoff.quantile(0.99),
                payoff.max(),
                len(payoff),
            ]
        )

    optdf["NumLimit"] = (
        np.abs(np.log(optdf["strike"] / optdf["underlying_close"]))
        / optdf["updownlimit"]
    ).round(2)
    optdf["TradingValue"] = (
        optdf["option_close"] * optdf["multiplier"] * optdf["volume"]
    )
    optdf[
        [
            "ExpectedPayoff",
            "MedianPayoff",
            "Q90Payoff",
            "Q99Payoff",
            "MaxPayoff",
            "DaysInSample",
        ]
    ] = optdf.apply(calculate_payoff, axis=1)
    # 计算期权的信用收取
    optdf["BuyCost"] = optdf["option_close"] * optdf["multiplier"] + optdf["commission"]
    # 计算期权的预期承保费
    optdf["ExpectedProfit"] = optdf["ExpectedPayoff"] - optdf["BuyCost"]
    optdf["MaxProfit"] = optdf["MaxPayoff"] - optdf["BuyCost"]
    optdf["Q99Profit"] = optdf["Q99Payoff"] - optdf["BuyCost"]
    optdf["Q90Profit"] = optdf["Q90Payoff"] - optdf["BuyCost"]
    optdf["MedianProfit"] = optdf["MedianPayoff"] - optdf["BuyCost"]

    optdf["ExpectedCostRet(C)"] = (
        optdf["ExpectedProfit"]
        / optdf["BuyCost"]
        # * 365
        # / optdf["cdtm"]
    )
    optdf["MaxCostRet(C)"] = (
        optdf["MaxProfit"]
        / optdf["BuyCost"]
        # * 365
        # / optdf["cdtm"]
    )
    optdf["Q99CostRet(C)"] = (
        optdf["Q99Profit"]
        / optdf["BuyCost"]
        # * 365
        # / optdf["cdtm"]
    )
    optdf["Q90CostRet(C)"] = (
        optdf["Q90Profit"]
        / optdf["BuyCost"]
        # * 365
        # / optdf["cdtm"]
    )
    optdf["MedianCostRet(C)"] = (
        optdf["MedianProfit"]
        / optdf["BuyCost"]
        # * 365
        # / optdf["cdtm"]
    )

    # 删除空值
    optdf = optdf.dropna()

    sql_cmd = f"""
    SELECT *
    FROM Gap_Ratio 
    """
    rvdf = pd.read_sql(sql_cmd, con=CCF.research)
    rvdf["dailyret"] = rvdf["close_main"] / rvdf["lastday_close"] - 1
    rvdf["dailyrv"] = np.square(rvdf["dailyret"])
    rvdf["minrv"] = rvdf["intraday_var"] + rvdf["gap_var"]
    rvdf["gapRatio"] = rvdf["gap_var"] / rvdf["minrv"]

    def calpara(df):
        df = df.sort_values("trading_date")
        miniAnnualRV = np.sqrt(df.tail(30)["minrv"].mean() * 243)
        gapRatio = df.tail(30)["gap_var"].sum() / df.tail(30)["minrv"].sum()
        kurtosisShort = df.tail(240)["dailyret"].kurt()
        kurtosisLong = df["dailyret"].kurt()
        return pd.Series(
            [miniAnnualRV, gapRatio, kurtosisShort, kurtosisLong],
            index=["1minAnnualRV", "gapRatio", "kurtosisShort", "kurtosisLong"],
        )

    summary = rvdf.groupby("product_id").apply(calpara).reset_index()
    sql_cmd = f"""
    WITH latest_vix AS (
        SELECT 
            product_id,
            vix,
            trading_date,
            future_price,
            PERCENT_RANK() OVER (PARTITION BY product_id ORDER BY vix) as vix_percentile,
            PERCENT_RANK() OVER (PARTITION BY product_id ORDER BY future_price) as price_percentile,
            COUNT(*) OVER (PARTITION BY product_id) as numVIXsamples
        FROM CommodityVIX
    )
    SELECT product_id, vix, vix_percentile, price_percentile, numVIXsamples
    FROM latest_vix 
    WHERE trading_date = '{date}'
    """
    vixdf = (
        pd.read_sql(sql_cmd, con=CCF.research)
        .drop_duplicates(subset=["product_id"])
        .reset_index(drop=True)
    )
    vixrvresult = pd.merge(summary, vixdf, on="product_id", how="outer")

    totalresult = pd.merge(
        optdf, vixrvresult, left_on="product", right_on="product_id", how="left"
    )
    totalresult.to_excel(f"E:\\KurStrategy\\dailySummary\\{date}\\{date}_longkurt.xlsx")


def main(date):
    # 读取期权价格数据
    # print(123123)
    optdf = findOptionPrice(date)
    # print(123123)
    # 设置期权价格数据的索引
    optdf.index = optdf["instrument_id"]
    # 调整保证金
    optdf["margin"] = optdf["margin"] * 1.2
    optdf["margin"] = optdf["margin"].round(0)
    # 计算期权的收益
    payoffmap = {}

    def calculate_payoff(row):
        ins_id = row["instrument_id"]
        product = row["product"]
        dtm = row["tdtm"]
        underlying_close = row["underlying_close"]
        strike = row["strike"]
        opt_typ = row["opt_typ"]
        # print(product, dtm, underlying_close, strike, opt_typ)
        try:
            payoff = (
                getPayoffSeries(product, dtm, underlying_close, strike, opt_typ)
                * row["multiplier"]
            )
            payoffmap[ins_id] = payoff
            return pd.Series(
                [
                    payoff.mean(),
                    payoff.quantile(0.95),
                    payoff.quantile(0.99),
                    payoff.max(),
                    len(payoff),
                    payoff.idxmax(),
                ]
            )
        except:
            payoff = pd.Series([np.nan, np.nan, np.nan, np.nan, np.nan, np.nan])
            return payoff

    optdf["NumLimit"] = (
        np.abs(np.log(optdf["strike"] / optdf["underlying_close"]))
        / optdf["updownlimit"]
    ).round(2)
    optdf["TradingValue"] = (
        optdf["option_close"] * optdf["multiplier"] * optdf["volume"]
    )
    optdf[
        [
            "ExpectedPayoff",
            "Q95Payoff",
            "Q99Payoff",
            "MaxPayoff",
            "DaysInSample",
            "worstDay",
        ]
    ] = optdf.apply(calculate_payoff, axis=1)
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
    # 计算期权的99%边际收益
    optdf["99MarginRet(C)"] = (
        (
            optdf["option_close"] * optdf["multiplier"]
            - optdf["Q99Payoff"]
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
    # 计算期权的99%边际收益
    optdf["99MarginRet(T)"] = (
        (
            optdf["option_close"] * optdf["multiplier"]
            - optdf["Q99Payoff"]
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

    optdf["Eret5Threshold"] = optdf["EMarginRet(C)"] > 0.05

    # 删除空值
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
    std_df = std_df[std_df["open_interest"] >= 200]
    # 筛选出最大收益为0且样本天数大于等于500的数据
    # std_df = std_df[(std_df["MaxPayoff"] == 0) & (std_df["DaysInSample"] >= 500)]
    std_df = std_df[(std_df["DaysInSample"] >= 500) & (std_df["Q99Payoff"] == 0)]

    #  输入为一行optdf，输出该行在该交易日14:55时间点的ask和bid
    def findOptionQuote(row):
        date = row["trading_date"]
        ins = row["instrument_id"]
        try:
            row = CCF.Option_Raw_Data(ins, date).iloc[-601]
            return float(row["Ask1"]), float(row["Bid1"])
        except:
            return np.nan, np.nan

    std_df["bid"] = std_df.apply(lambda x: findOptionQuote(x)[1], axis=1)
    # 生成excel数据
    exceldf = std_df[
        [
            "underlying_instr_id",
            "product",
            "option_close",
            "sector",
            "NumLimit",
            "EMarginRet(C)",
            "MaxPayoff",
            "worstDay",
            "margin",
            "delta",
            "tdtm",
            "cdtm",
            "bid",
        ]
    ].dropna()
    exceldf = exceldf[exceldf["bid"] > 0].reset_index()
    exceldf["EMarginRet(C)"] = (exceldf["EMarginRet(C)"] * 100).round(2)
    # exceldf["EMarginRet(T)"] = (exceldf["EMarginRet(T)"] * 100).round(2)
    exceldf["delta"] = (exceldf["delta"]).round(2)
    exceldf["MaxPayoff"] = (exceldf["MaxPayoff"]).round(2)
    # undrownum = exceldf.groupby("underlying_instr_id").size()
    # undmeanret = (
    #     exceldf.groupby("underlying_instr_id")["EMarginRet(T)"]
    #     .mean()
    #     .sort_values(ascending=False)
    # )
    result = {}
    exceldf = (
        exceldf.sort_values(by="delta", ascending=False)
        .groupby(["sector", "cdtm", "underlying_instr_id", "instrument_id"])
        .first()
    )
    for sec in std_df["sector"].unique():
        try:
            result[sec] = exceldf.loc[[sec], :]
        except:
            pass
    # cnt = 0
    # sett = []
    # for und in undmeanret.index:
    #     thisnum = undrownum[und]
    #     if thisnum + cnt > 120:
    #         result.append(exceldf.loc[(sett, slice(None)), :])
    #         sett = [und]
    #         cnt = thisnum
    #     else:
    #         sett.append(und)
    #         cnt += thisnum
    # result.append(exceldf.loc[(sett, slice(None)), :])

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
        rowjs["product_id"] = row["product"]
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
    direc = f"E:\\KurStrategy\\dailySummary\\{date}\\"
    Path(direc).mkdir(parents=True, exist_ok=True)
    with open(direc + f"{date}_jssave.json", "w") as f:
        json.dump(jsonoutput, f)
    # 保存excel数据
    optdf.to_excel(direc + f"{date}_totalSet.xlsx")
    std_df.to_excel(direc + f"{date}_selectSet.xlsx")
    # 生成excel图片
    direc = f"E:\\KurStrategy\\dailySummary\\{date}\\picfile\\"
    Path(direc).mkdir(parents=True, exist_ok=True)
    for i in result:
        dfi.export(
            result[i],
            f"{direc}{date}_{i}.png",
            fontsize=2,
            dpi=900,
            table_conversion="chrome",
            chrome_path="C:\Program Files\Google\Chrome Dev\Application\chrome.exe",
            max_rows=-1,
        )

    longKurtTemp(date)


# main("20250723")
