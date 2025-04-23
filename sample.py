import py_vollib.black_scholes_merton.implied_volatility as BSMiv
import py_vollib.black_scholes_merton.greeks.analytical as BSMgreeks
import numpy as np


# 从价格反推IV，r可设置为0
def IV(price, F, K, t, r, flag):
    try:
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


# 从IV反推价格
def CalOptPrice(iv, F, K, t, r, flag):
    return BSMiv.black_scholes_merton(flag, F, K, t, r, iv, 0)


# 计算Greeks
def IV_GREEK(price, S, K, t, r, flag):
    """

    :param price:
    :param S:
    :param K:
    :param t:
    :param r:
    :param flag:
    :return: 以list形式返回[iv, delta, gamma, vega, theta]
    """
    q = 0
    try:
        iv = BSMiv.implied_volatility(
            price, S, K, t, r, 0, flag
        )  # 个别期权求得的iv是无穷大，无效值，也无法求Greeks
        sigma = iv
        delta = BSMgreeks.delta(flag, S, K, t, r, sigma, 0)
        gamma = BSMgreeks.gamma(flag, S, K, t, r, sigma, 0)
        vega = BSMgreeks.vega(flag, S, K, t, r, sigma, 0)
        theta = BSMgreeks.theta(flag, S, K, t, r, sigma, 0)
    except:
        # print(f'invalid implied volatility! {price, S, K, t, r, q, flag}')
        return [np.nan, np.nan, np.nan, np.nan, np.nan]

    if iv > 1:
        return [np.nan, np.nan, np.nan, np.nan, np.nan]
    else:
        if np.isnan(gamma):
            gamma = 0
        return [iv, delta, gamma, vega, theta]


if __name__ == "__main__":
    # 对于有行情源的数据，取ru2505为案例
    ### RU2505P13500,市价为18
    opt_price = 8.3
    typ = "p"
    underlying_price = 714.5
    ttm = 83 / 243
    r = 0
    strike = 600
    ### 计算IV
    iv = IV(opt_price, underlying_price, strike, ttm, r, typ)
    ### 计算Greeks,注意乘数效应
    multi = 100
    greeks = IV_GREEK(opt_price, underlying_price, strike, ttm, r, typ)
    print("一手RU2505P13500的价格为", opt_price * multi)
    print("一手RU2505P13500的iv为", greeks[0])
    print("一手RU2505P13500的delta为", greeks[1] * multi)
    print("一手RU2505P13500的gamma为", greeks[2] * multi)
    print("一手RU2505P13500的vega为", greeks[3] * multi)
    print("一手RU2505P13500的theta为", greeks[4] * multi)
    print("dollardelta", greeks[1] * multi * underlying_price)
    # print("dollardelta", greeks[1] * multi * underlying_price)
    # print("dollardelta", greeks[1] * multi * underlying_price)

    # print()

    # ### 针对没有定义的合约，如RU2505P14375
    # ### 可用IV（默认为昨日vix）计算价格，其余参数假设都相同
    # strike2 = 14375
    # opt_price2 = CalOptPrice(iv, underlying_price, strike2, ttm, r, typ)
    # print("一手RU2505P14375的价格为", opt_price2 * multi)

    # ### 计算Greeks
    # greeks2 = IV_GREEK(opt_price2, underlying_price, strike2, ttm, r, typ)
    # print("一手RU2505P14375的iv为", greeks2[0])
    # print("一手RU2505P14375的delta为", greeks2[1] * multi)
    # print("一手RU2505P14375的gamma为", greeks2[2] * multi)
    # print("一手RU2505P14375的vega为", greeks2[3] * multi)
    # print("一手RU2505P14375的theta为", greeks2[4] * multi)
    # print()

    # ### 假设现在有组合【一手RU2505P13500，一手RU2505P14375】
    # ### 计算组合的delta，gamma，vega，theta
    # delta = greeks[1] * multi + greeks2[1] * multi
    # gamma = greeks[2] * multi + greeks2[2] * multi
    # vega = greeks[3] * multi + greeks2[3] * multi
    # theta = greeks[4] * multi + greeks2[4] * multi
    # priceall = opt_price * multi + opt_price2 * multi
    # print("组合的价值为", priceall)
    # print("组合的delta为", delta)
    # print("组合的gamma为", gamma)
    # print("组合的vega为", vega)
    # print("组合的theta为", theta)

    ### 扩展两个概念：
    # 净delta为单纯函数计算的delta
    ### dollar delta为当前期权delta的dollar市值，为净delta * option_multiplier * underlying_price
    ### lots delta为当前期权的delta换算为underlying的手数，为净delta * option_multiplier / underlying_multiplier
