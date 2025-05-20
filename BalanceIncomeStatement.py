import pandas as pd
import numpy as np
import commodity_common_functions as CCF
import seaborn as sns
import dataframe_image as dfi
from pathlib import Path
import json
import os
import datetime as dt
import logging
from datetime import datetime
import OptionRiskMetrixETF as ORME
import OptionRiskMetrix as ORM


def readEXEPORTportfolio():
    sqlcmd = f"""
    SELECT *
    FROM portfolio
    """
    df = pd.read_sql(sql=sqlcmd, con=CCF.EXEPORT_engine)
    result = {}
    for ind, row in df.iterrows():
        name = row["portfolio_name"]
        inslst = row["instruments"].split(",")
        poslst = row["trade_ratio"].split(",")
        temp = {}
        for i, j in zip(inslst, poslst):
            temp[i] = int(float(j)) * -1
        result[name] = {}
        result[name]["portfolio"] = temp
        result[name]["multiplier"] = row["portfolio_multiple"]
        result[name]["recentins"] = sorted(inslst)[0]
    inslst = [i["recentins"] for i in result.values()]
    SQL_cmd = f"""
    SELECT
        i.instrument_id,
        i.expiredate
    FROM instrument i
    WHERE i.instrument_id IN {tuple(inslst)}
    """
    instrument_info = pd.read_sql(sql=SQL_cmd, con=CCF.market_base)
    instrument_info = instrument_info.set_index("instrument_id")["expiredate"].to_dict()
    for i in result.keys():
        result[i]["expiredate"] = (
            instrument_info[result[i]["recentins"]]
            if result[i]["recentins"] in instrument_info
            else ""
        )
    return result


stgtreaddict = {}


def readALLSTGTRADE(begin_tag):
    if begin_tag in stgtreaddict:
        return stgtreaddict[begin_tag].copy()
    sqlcmd = f"""
    SELECT operator, traded_time, init_trading_day, fund_name, portfolio_name,stg_tags, direction, volume_traded, traded_price, commission
    FROM stg_trade_raw
    WHERE (status = 'DONE' or status = 'PORT_DONE') and init_trading_day >= '20250313' and stg_tags like '{begin_tag}%%'
    """
    df = pd.read_sql(sql=sqlcmd, con=CCF.EXEPORT_engine)
    sqlcmd = f"""
    SELECT operator, traded_time, init_trading_day, fund_name, portfolio_name,stg_tags, direction, volume_traded, traded_price, commission
    FROM stg_trade_raw
     WHERE (status = 'DONE' or status = 'PORT_DONE') and portfolio_name in {tuple(df['portfolio_name'].unique())}
    """
    df2 = pd.read_sql(sql=sqlcmd, con=CCF.EXEPORT_engine)
    stgtreaddict[begin_tag] = df2
    return df2.copy()


portfoliosFROMEXEPORT = readEXEPORTportfolio()


def transferToDict(df):
    result = {}
    for ind, row in df.iterrows():
        stgname = row["策略名"]
        if stgname not in result:
            result[stgname] = {}
            result[stgname]["账户"] = row["账户"]
            result[stgname]["持仓"] = row["持仓"]
            result[stgname]["持仓均价"] = row["持仓均价"]
        else:
            prevpos = result[stgname]["持仓"]
            thispos = row["持仓"]
            result[stgname]["持仓均价"] = (
                prevpos * result[stgname]["持仓均价"] + thispos * row["持仓均价"]
            ) / (prevpos + thispos)
            result[stgname]["持仓"] = prevpos + thispos
    return result


def mergePos(prev_df, today_df, date):
    required_columns = ["账户", "策略名", "持仓", "持仓均价"]
    if not all(col in prev_df.columns for col in required_columns):
        raise Exception("prev_df must have columns: 账户, 策略名, 持仓, 持仓均价")
    if not all(col in today_df.columns for col in required_columns):
        raise Exception("today_df must have columns: 账户, 策略名, 持仓, 持仓均价")
    if len(prev_df["账户"].unique()) > 1:
        raise Exception("prev_df must have only one account")
    if len(today_df["账户"].unique()) > 1:
        raise Exception("today_df must have only one account")
    if len(prev_df) > 0 and len(today_df) > 0:
        if prev_df["账户"].unique()[0] != today_df["账户"].unique()[0]:
            raise Exception("prev_df and today_df must have the same account")
    prev_dict = transferToDict(prev_df)
    today_trade = transferToDict(today_df)
    today_result = {}
    for stgname in today_trade:
        ### 首先处理trade
        if stgname not in portfoliosFROMEXEPORT:
            print()
            print(f"{stgname} not in portfoliosFROMEXEPORT")
            continue
        stgdetail = portfoliosFROMEXEPORT[stgname]
        multiplier = stgdetail["multiplier"]
        if stgname not in prev_dict:
            today_result[stgname] = today_trade[stgname].copy()
            today_trade[stgname]["方向"] = "开仓"
            today_trade[stgname]["PNL"] = 0
        else:
            thisstgpos = prev_dict[stgname]["持仓"] + today_trade[stgname]["持仓"]
            if (today_trade[stgname]["持仓"] * prev_dict[stgname]["持仓"]) > 0:
                # Same direction - update position and average price
                today_result[stgname] = today_trade[stgname].copy()
                today_result[stgname]["持仓"] = thisstgpos
                today_result[stgname]["持仓均价"] = (
                    prev_dict[stgname]["持仓"] * prev_dict[stgname]["持仓均价"]
                    + today_trade[stgname]["持仓"] * today_trade[stgname]["持仓均价"]
                ) / thisstgpos
                today_trade[stgname]["方向"] = "加仓"
                today_trade[stgname]["PNL"] = 0
            else:
                if abs(today_trade[stgname]["持仓"]) > abs(prev_dict[stgname]["持仓"]):
                    today_result[stgname] = today_trade[stgname].copy()
                    today_result[stgname]["持仓"] = thisstgpos
                    today_result[stgname]["持仓均价"] = today_trade[stgname]["持仓均价"]
                    today_trade[stgname]["方向"] = "平昨反开"
                    today_trade[stgname]["PNL"] = (
                        (
                            today_trade[stgname]["持仓均价"]
                            - prev_dict[stgname]["持仓均价"]
                        )
                        * prev_dict[stgname]["持仓"]
                        * multiplier
                    )
                elif abs(today_trade[stgname]["持仓"]) < abs(
                    prev_dict[stgname]["持仓"]
                ):
                    today_result[stgname] = today_trade[stgname].copy()
                    today_result[stgname]["持仓"] = thisstgpos
                    today_result[stgname]["持仓均价"] = prev_dict[stgname]["持仓均价"]
                    today_trade[stgname]["方向"] = "部分平仓"
                    today_trade[stgname]["PNL"] = (
                        (
                            today_trade[stgname]["持仓均价"]
                            - prev_dict[stgname]["持仓均价"]
                        )
                        * today_trade[stgname]["持仓"]
                        * -1
                        * multiplier
                    )
                else:
                    today_trade[stgname]["方向"] = "全平"
                    today_trade[stgname]["PNL"] = (
                        (
                            today_trade[stgname]["持仓均价"]
                            - prev_dict[stgname]["持仓均价"]
                        )
                        * prev_dict[stgname]["持仓"]
                        * multiplier
                    )
    for stgname in prev_dict:
        if stgname not in today_trade:
            stgdetail = portfoliosFROMEXEPORT[stgname]
            multiplier = stgdetail["multiplier"]
            expiredate = portfoliosFROMEXEPORT[stgname]["expiredate"]
            if expiredate <= date:
                today_trade[stgname] = prev_dict[stgname].copy()
                today_trade[stgname]["PNL"] = (
                    today_trade[stgname]["持仓均价"]
                    * today_trade[stgname]["持仓"]
                    * -1
                    * multiplier
                )
                today_trade[stgname]["持仓"] = today_trade[stgname]["持仓"] * -1
                today_trade[stgname]["持仓均价"] = 0
                today_trade[stgname]["方向"] = "自然到期"
                continue
            else:
                today_result[stgname] = prev_dict[stgname].copy()
    today_result = (
        pd.DataFrame(today_result).T.reset_index().rename(columns={"index": "策略名"})
    )
    today_trade = (
        pd.DataFrame(today_trade).T.reset_index().rename(columns={"index": "策略名"})
    )
    if len(today_result) == 0:
        today_result = pd.DataFrame(columns=["账户", "策略名", "持仓", "持仓均价"])
    if len(today_trade) == 0:
        today_trade = pd.DataFrame(
            columns=["账户", "策略名", "持仓", "持仓均价", "方向", "PNL"]
        )
    return today_result, today_trade

    # prev_df['持仓均价'] = prev_df['持仓均价'].fillna(prev_df['持仓均价'].mean())
    # today_df['持仓均价'] = today_df['持仓均价'].fillna(today_df['持仓均价'].mean())
    # return pd.concat([prev_df, today_df])


def generateDaysition(date, begin_tag):
    if date < "20250312":
        raise Exception("date must be greater than 20250312")
    if date == "20250312":
        temp = pd.DataFrame(columns=["账户", "策略名", "持仓", "持仓均价"])
        path = f"E://ExePort//{begin_tag}//{date}//"
        CCF.mkdir(path)
        temp.to_excel(f"{path}{date}_position.xlsx")
        return temp
    portfoliosFROMEXEPORT = readEXEPORTportfolio()
    allstgtrade = readALLSTGTRADE(begin_tag)
    allstgtrade = allstgtrade[
        allstgtrade["portfolio_name"].isin(portfoliosFROMEXEPORT.keys())
    ]
    allstgtrade["trading"] = (allstgtrade["direction"] == 1) * 2 - 1
    allstgtrade["trading"] = allstgtrade["trading"] * allstgtrade["volume_traded"]
    allstgtrade["traded_price"] = allstgtrade["traded_price"] * -1
    # Group by fund_name and sort by traded_time
    allstgtrade = allstgtrade.sort_values("traded_time")
    today_trade = allstgtrade[allstgtrade["init_trading_day"] == date]
    tempdf = today_trade[
        ["init_trading_day", "fund_name", "portfolio_name", "trading", "traded_price"]
    ]
    tempdf.columns = ["日期", "账户", "策略名", "持仓", "持仓均价"]
    lasttradeday = CCF.tradingDay[CCF.tradingDay < date].max()
    try:
        lastdaypos = pd.read_excel(
            f"E://ExePort//{begin_tag}//{lasttradeday}//{lasttradeday}_position.xlsx"
        )
    except:
        lastdaypos = generateDayPosition(lasttradeday, begin_tag)
    acc_lst = [
        "招享1号",
        "招享2号",
        "招享3号",
        "招享通胀1号",
        "风险均配1号",
        "500指数先锋",
        "觉醒1号",
        "CTA1号",
        "国债指数先锋",
        "星原1号",
    ]
    posdf = pd.DataFrame(columns=["账户", "策略名", "持仓", "持仓均价"])
    tradedf = pd.DataFrame(
        columns=["账户", "策略名", "方向", "持仓", "持仓均价", "PNL"]
    )
    for acc in acc_lst:
        today = date
        acctodaytrade = tempdf[(tempdf["账户"] == acc)]
        if len(acctodaytrade) == 0:
            acctodaytrade = pd.DataFrame(columns=["账户", "策略名", "持仓", "持仓均价"])
        acclastdaypos = lastdaypos[lastdaypos["账户"] == acc]
        thisposdf, thistradedf = mergePos(acclastdaypos, acctodaytrade, today)
        posdf = pd.concat([posdf, thisposdf])
        tradedf = pd.concat([tradedf, thistradedf])
    tradedf.rename(columns={"持仓均价": "交易价格", "持仓": "交易手数"}, inplace=True)
    acclastdaypos.reset_index(drop=True).to_excel(
        f"E://ExePort//{begin_tag}//{date}//{date}_lastdaypos.xlsx"
    )
    posdf.reset_index(drop=True).to_excel(
        f"E://ExePort//{begin_tag}//{date}//{date}_position.xlsx"
    )
    tradedf.reset_index(drop=True).to_excel(
        f"E://ExePort//{begin_tag}//{date}//{date}_trade.xlsx"
    )
    with open(
        f"E://ExePort//{begin_tag}//{date}//{date}_portfoliosFROMEXEPORT.json", "w"
    ) as f:
        json.dump(portfoliosFROMEXEPORT, f)
    # sumdf = (
    #     tradedf.groupby("账户")["PNL"].sum().sort_values(ascending=False).reset_index()
    # )
    # cm = sns.color_palette("rocket", as_cmap=True)
    # a = sumdf.style.background_gradient(cmap=cm, subset="PNL").format(precision=2)
    # try:
    #     dfi.export(
    #         a,
    #         f"E://ExePort//{begin_tag}//{date}//{date}_tradesummary.png",
    #         fontsize=2,
    #         dpi=900,
    #         table_conversion="chrome",
    #         chrome_path="C:\Program Files\Google\Chrome Dev\Application\chrome.exe",
    #         max_rows=-1,
    #     )
    # except:
    #     print(f"{date} {begin_tag} trade summary failed")

    print(f"{date} {begin_tag} done")
    return posdf


def summaryAllTrade(begin_tag):
    # Get base director
    base_dir = f"E:\\ExePort\\{begin_tag}\\"

    # Initialize empty list to store dataframes
    dfs = pd.DataFrame()

    # Walk through all subdirectories
    for root, dirs, files in os.walk(base_dir):
        # Find all xlsx files containing 'trade' in filename
        xlsx_files = [f for f in files if f.endswith(".xlsx") and "trade" in f.lower()]

        # Read and append each xlsx file
        for file in xlsx_files:
            file_path = os.path.join(root, file)
            df = pd.read_excel(file_path)
            # Drop first column
            df = df.iloc[:, 1:]
            dfs = pd.concat([dfs, df])
    dfs = dfs.reset_index(drop=True)
    sumdf = dfs.groupby("账户")["PNL"].sum().sort_values(ascending=False).reset_index()
    cm = sns.color_palette("rocket", as_cmap=True)
    a = sumdf.style.background_gradient(cmap=cm, subset="PNL").format(precision=2)
    dfi.export(
        a,
        f"E:\\ExePort\\{begin_tag}\\summary.png",
        fontsize=2,
        dpi=900,
        table_conversion="chrome",
        chrome_path="C:\Program Files\Google\Chrome Dev\Application\chrome.exe",
        max_rows=-1,
    )
    dfs.to_excel(f"E:\\ExePort\\{begin_tag}\\summary.xlsx")
    return dfs


# generateDayPosition("20250515", "kurt")


if __name__ == "__main__":
    # summaryAllTrade("kurt")

    today = datetime.now().strftime("%Y%m%d")
    # today = "20250515"
    generateDayPosition(today, "kurt")
