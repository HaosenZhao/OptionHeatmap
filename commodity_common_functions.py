"""
商品期权相关程序共用的基础函数

2021/12/10

将不同品种的 risk free rate 设为不同值，即 0.025 * margin rate
"""

from sqlalchemy import create_engine
import py_vollib.black.implied_volatility as BLKiv
import py_vollib.black.greeks.analytical as BLKgreeks
import py_vollib.black_scholes_merton.implied_volatility as BSMiv
import py_vollib.black_scholes_merton.greeks.analytical as BSMgreeks
import numpy as np
import pandas as pd
import datetime as dt
import math
import copy
import os

# from scipy import interpolate


# 打开数据库连接（ip/数据库用户名/登录密码/数据库名）
username = "researcher"
host = "192.168.2.4"
pwd = "Market_re"

# 用sqlalchemy构建数据库链接engine,连接market base
database1 = "wind_data"
connect_info1 = "mysql+pymysql://{}:{}@{}:{}/{}?charset=utf8".format(
    username, pwd, host, "3306", database1
)
wind_data = create_engine(connect_info1)

database2 = "market_base"
connect_info2 = "mysql+pymysql://{}:{}@{}:{}/{}?charset=utf8".format(
    username, pwd, host, "3306", database2
)
market_base = create_engine(connect_info2)

database3 = "research"
connect_info3 = "mysql+pymysql://{}:{}@{}:{}/{}?charset=utf8".format(
    username, pwd, host, "3306", database3
)
research = create_engine(connect_info3)

database4 = "std_market_data"
connect_info4 = "mysql+pymysql://{}:{}@{}:{}/{}?charset=utf8".format(
    username, pwd, host, "3306", database4
)
std_market_data = create_engine(connect_info4)

username5 = "pmuser"
host5 = "192.168.2.4"
pwd5 = "Efpm2021$"
database5 = "efpm"
connect_info = "mysql+pymysql://{}:{}@{}:{}/{}?charset=utf8".format(
    username5, pwd5, host5, "3306", database5
)
efpm = create_engine(connect_info)


username = "tradesysreader"
host = "rm-uf6w0x297e0u6e89e7o.mysql.rds.aliyuncs.com"
pwd = "AFt4VFDqFKRAJDw"

# 用sqlalchemy构建数据库链接engine,连接market base
database1 = "futures_base"
connect_info1 = "mysql+pymysql://{}:{}@{}:{}/{}?charset=utf8".format(
    username, pwd, host, "3306", database1
)
EXEPORT_engine = create_engine(connect_info1)

tradingday_path = "E:tradingDay.csv"
tradingDay = pd.read_csv(tradingday_path, dtype={"trading_day": object})
tradingDay = np.array(tradingDay.trading_day)


def Ftp_Path(tradingdate):
    today_str = dt.date.today().strftime(format="%Y%m%d")
    if tradingdate == today_str:
        path = "ftp://192.168.2.4/"
    else:
        path = "ftp://192.168.2.111/"
    return path


def mkdir(folder):
    # 判断路径是否存在
    # 存在     True
    # 不存在   False
    isExists = os.path.exists(folder)

    # 判断结果
    if not isExists:
        # 如果不存在则创建目录
        # 创建目录操作函数
        os.makedirs(folder)
        print(f"{folder}  创建成功")
    else:
        # 如果目录存在则不创建，并提示目录已存在
        print(f"{folder}  目录已存在")


# 取出股指underlying在交易日tradingdate的所有期权合约信息
# wind_code,instrument_id,option_type,strike_price,listed_date,expire_date,trading_date,delivery_month,calendar_ttm
def Option_Info_With_Same_Underlying(underlying, tradingdate):
    """
    tradingdate 当天仍在存续期的、标的资产为 underlying 的所有期权合约的基础信息
    :param underlying:
    :param tradingdate:
    :return: DataFrame 列包括wind_code,instrument_id,option_type,strike_price,listed_date,expire_date,trading_date,
    delivery_month,trading_ttm
    """
    SQL_cmd = """SELECT instrument_id, 
    COALESCE(instrument_code, instrument_id) instrument_code, 
    options_type, strike_price, opendate, expiredate 
    FROM instrument 
    WHERE IF(LEFT(underlying_instr_id,2)='IO', '000300', underlying_instr_id)='%s'
    AND expiredate >= '%s'
    AND opendate <= '%s'
    AND RIGHT(RTRIM(instrument_name),1)!='A'
    AND product_class IN ('2')
    """ % (
        underlying,
        tradingdate,
        tradingdate,
    )

    info = pd.read_sql(sql=SQL_cmd, con=market_base)

    # 去除空格
    info = info.replace(" ", "", regex=True)
    info.loc[:, "options_type"] = info.options_type.apply(
        lambda x: "c" if x == "1" else "p"
    )
    info.loc[:, "trading_date"] = [tradingdate] * len(info)
    info.loc[:, "delivery_month"] = info.expiredate.apply(lambda x: x[2:6])
    #     info['calendar_ttm'] = pd.to_datetime(info['expiredate']) - pd.to_datetime(info['trading_date'])
    #     info['calendar_ttm'] = info['calendar_ttm'].apply(lambda x: x.days)
    info.loc[:, "trading_ttm"] = info.apply(
        lambda x: np.where(tradingDay == x["expiredate"])[0][0]
        - np.where(tradingDay == x["trading_date"])[0][0],
        axis=1,
    )

    info = info.rename(
        columns={
            "instrument_id": "wind_code",
            "instrument_code": "instrument_id",
            "options_type": "option_type",
            "opendate": "listed_date",
            "expiredate": "expire_date",
        }
    )

    return info


def instrument_info(inst_id: str):
    """
    给定合约id，以series格式返回其各项基础信息
    :param inst_id:
    :return: series 包含字段 instrument_code, options_type, strike_price, opendate, expiredate, underlying_instr_id, delivery_month
    """
    SQL_cmd = (
        """SELECT COALESCE(instrument_code, instrument_id) instrument_code, 
    options_type, strike_price, opendate, expiredate, 
    IF(LEFT(underlying_instr_id,2)='IO', '000300', underlying_instr_id) underlying_instr_id 
    FROM instrument 
    WHERE instrument_id='%s' 
    """
        % inst_id
    )
    info = pd.read_sql(sql=SQL_cmd, con=market_base)
    info.replace(" ", "", regex=True, inplace=True)  # 去除空格
    info.loc[:, "options_type"] = info.options_type.apply(
        lambda x: "c" if x == "1" else "p"
    )
    info.loc[:, "delivery_month"] = info.expiredate.apply(lambda x: x[2:6])
    info.reset_index(drop=True, inplace=True)
    return info.loc[0, :]


def calculate_trading_days(begin_date: str, end_date: str):
    """
    计算两个日期之间有多少个交易日，包括结束日不包括起始日
    :param begin_date:
    :param end_date:
    :return:
    """
    trading_days = (
        np.where(tradingDay == end_date)[0][0]
        - np.where(tradingDay == begin_date)[0][0]
    )
    return trading_days


# 取出underlying在交易日tradingdate的交易数据
def Spot_Raw_Data(underlying: str, tradingdate: str):
    """
    :param underlying:
    :param tradingdate:
    :return: dataframe 包含字段 id, seq_no, future_bid1, future_ask1, future_mid_price
    """
    future_path = Ftp_Path(tradingdate)
    future_path = f"{future_path}ctp_std_data/{tradingdate}/{underlying}.csv"
    FutureData = pd.read_csv(
        future_path,
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

    # FutureData.loc[:, 'FutureMidPrice'] = 0.5 * (FutureData['bid_price1'] + FutureData['ask_price1'])
    # 考虑无ask/bid报价的场景，如涨跌停
    FutureData.loc[:, "FutureMidPrice"] = FutureData.apply(
        lambda row: (
            max(row["bid_price1"], row["ask_price1"])
            if row["bid_price1"] * row["ask_price1"] == 0
            else 0.5 * (row["bid_price1"] + row["ask_price1"])
        ),
        axis=1,
    )
    FutureData.rename(
        columns={"bid_price1": "FutureBid1", "ask_price1": "FutureAsk1"}, inplace=True
    )

    return FutureData


# 取出期权合约InstrumentID在tradingdate的交易数据
def Option_Raw_Data(wind_code: str, tradingdate: str):
    """

    :param wind_code:
    :param tradingdate:
    :return: dataframe 包含字段 id, seq_no, Bid1, Ask1, MidPrice
    """
    future_path = Ftp_Path(tradingdate)
    option_data = f"{future_path}ctp_std_data/{tradingdate}/{wind_code}.csv"
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


def Risk_Free_Rate(underlying):
    sql_cmd = (
        """
    SELECT instrument_id, long_margin_ratio, short_margin_ratio FROM instrument WHERE instrument_id='%s'
    """
        % underlying
    )
    margin_ratio = pd.read_sql(sql_cmd, con=market_base)
    r = (
        0.025
        * 0.5
        * (
            margin_ratio.loc[0, "long_margin_ratio"]
            + margin_ratio.loc[0, "short_margin_ratio"]
        )
    )
    print(f"{underlying} r={r}")
    return r


# 计算IV
def IV(price, F, K, t, r, flag):
    try:
        # iv = BLKiv.implied_volatility(price, F, K, t, r, flag)  # 个别期权求得的iv是无穷大，无效值，也无法求Greeks
        iv = BSMiv.implied_volatility(
            price, F, K, t, r, 0, flag
        )  # 个别期权求得的iv是无穷大，无效值，也无法求Greeks
    except:
        return np.nan
    if iv > 2:
        # print('IV 大于2')
        return np.nan
    else:
        return iv


# 计算IV和Greeks
def IV_GREEK(price, S, K, t, r, q, flag):
    """

    :param price:
    :param S:
    :param K:
    :param t:
    :param r:
    :param q:
    :param flag:
    :return: 以list形式返回[iv, delta, gamma, vega, theta]
    """
    q = 0
    try:
        iv = BSMiv.implied_volatility(
            price, S, K, t, r, q, flag
        )  # 个别期权求得的iv是无穷大，无效值，也无法求Greeks
        sigma = iv
        delta = BSMgreeks.delta(flag, S, K, t, r, sigma, q)
        gamma = BSMgreeks.gamma(flag, S, K, t, r, sigma, q)
        vega = BSMgreeks.vega(flag, S, K, t, r, sigma, q)
        theta = BSMgreeks.theta(flag, S, K, t, r, sigma, q)
    except:
        # print(f'invalid implied volatility! {price, S, K, t, r, q, flag}')
        return [np.nan, np.nan, np.nan, np.nan, np.nan]

    if iv > 10:
        return [np.nan, np.nan, np.nan, np.nan, np.nan]
    else:
        if np.isnan(gamma):
            gamma = 0
        return [iv, delta, gamma, vega, theta]


def Instrument_Data(inst_id: str, tradingdate: str, time_interval: int = 0):
    """
    返回合约在一个交易日的价格和希腊值数据
    :param inst_id:
    :param tradingdate:
    :param time_interval: 将数据切片成time_interval分钟频率的数据，default value = 0
    :return: dataframe, 期权包含字段 id, seq_no, Bid1, Ask1, MidPrice, Spot, ttm, IV, Delta, Gamma, Vega, Theta；期货则没有Spot和ttm字段
    """
    ftp_path = Ftp_Path(tradingdate)
    if len(inst_id) > 6:  # 商品期权
        try:
            # inst_Data为option inst_id的intraday data
            inst_data = Option_Raw_Data(inst_id, tradingdate)
        except:
            print(f"{inst_id}合约在{tradingdate}无标准化数据")
            return

        info = instrument_info(inst_id)
        flag, K, underlying, expire_date = info[
            ["options_type", "strike_price", "underlying_instr_id", "expiredate"]
        ]
        # spot data为underlying的intraday data
        spot_data = Spot_Raw_Data(underlying, tradingdate)
        inst_data.loc[:, "Spot"] = spot_data.loc[:, "FutureMidPrice"]
        total_ticks = spot_data["seq_no"].max()
        tick_interval = time_interval * 120 if time_interval > 0 else 1
        sliced_seq = np.arange(0, total_ticks + 1, tick_interval)  # 数据切片
        inst_data = inst_data.query("seq_no in @sliced_seq").copy()

        ttm = calculate_trading_days(tradingdate, expire_date)
        r = Risk_Free_Rate(underlying)

        q = 0
        inst_data.loc[:, "ttm"] = inst_data.seq_no.apply(
            lambda x: ((total_ticks - x) / total_ticks + ttm) / 243
        )

        inst_data_1 = (
            inst_data.apply(
                lambda x: pd.Series(
                    IV_GREEK(x["MidPrice"], x["Spot"], K, x["ttm"], r, q, flag)
                )
            ),
        )
        inst_data = pd.concat([inst_data, inst_data_1], axis=1)

    else:  # 期货
        dir_name = "ctp"

        try:
            inst_path = f"{ftp_path}{dir_name}_std_data/{tradingdate}/{inst_id}.csv"
            inst_data = pd.read_csv(
                inst_path,
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
        except:
            print(f"{inst_id}合约在{tradingdate}无标准化数据")
            return

        inst_data.rename(
            columns={"bid_price1": "Bid1", "ask_price1": "Ask1"}, inplace=True
        )
        total_ticks = inst_data["seq_no"].max()
        tick_interval = time_interval * 120 if time_interval > 0 else 1
        sliced_seq = np.arange(0, total_ticks + 1, tick_interval)  # 数据切片
        inst_data = inst_data.query("seq_no in @sliced_seq")  # 数据切片
        inst_data.loc[:, "MidPrice"] = 0.5 * (inst_data.Bid1 + inst_data.Ask1)
        inst_data.loc[:, "Spot"] = inst_data.MidPrice
        inst_data.loc[:, "IV"] = [0] * len(inst_data)
        inst_data.loc[:, "Delta"] = [1] * len(inst_data)
        inst_data.loc[:, "Gamma"] = [0] * len(inst_data)
        inst_data.loc[:, "Vega"] = [0] * len(inst_data)
        inst_data.loc[:, "Theta"] = [0] * len(inst_data)

    return inst_data
