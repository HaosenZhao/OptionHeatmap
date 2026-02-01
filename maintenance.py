#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据维护脚本
从 OpenCTP API 获取期权合约数据，自动维护 expire_date.json 和 trade_para.json
"""

import json
import requests
from datetime import datetime


# API 端点
OPTION_API_URL = "http://dict.openctp.cn/instruments?types=option"
FUTURES_API_URL = "http://dict.openctp.cn/instruments?types=futures"

# 配置文件路径
EXPIRE_DATE_FILE = "expire_date.json"
TRADE_PARA_FILE = "trade_para.json"

# ProductID 特殊映射 (期货 -> 期权)
# 股指期货的保证金率需要映射到对应的股指期权
PRODUCT_ID_MAPPING = {
    "IF": "IO",  # 沪深300期货 -> 沪深300期权
    "IM": "MO",  # 中证1000期货 -> 中证1000期权
    "IH": "HO",  # 上证50期货 -> 上证50期权
}


def fetch_option_instruments():
    """
    获取期权合约数据
    返回: API返回的期权合约列表
    """
    print("正在获取期权合约数据...")
    try:
        response = requests.get(OPTION_API_URL, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("rsp_code") != 0:
            raise Exception(f"API返回错误: {data.get('rsp_message')}")

        instruments = data.get("data", [])
        print(f"成功获取 {len(instruments)} 条期权合约数据")
        return instruments
    except requests.RequestException as e:
        raise Exception(f"获取期权数据失败: {e}")


def fetch_futures_instruments():
    """
    获取期货合约数据（用于获取保证金率）
    返回: API返回的期货合约列表
    """
    print("正在获取期货合约数据...")
    try:
        response = requests.get(FUTURES_API_URL, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("rsp_code") != 0:
            raise Exception(f"API返回错误: {data.get('rsp_message')}")

        instruments = data.get("data", [])
        print(f"成功获取 {len(instruments)} 条期货合约数据")
        return instruments
    except requests.RequestException as e:
        raise Exception(f"获取期货合约数据失败: {e}")


def convert_date_format(date_str):
    """
    转换日期格式: YYYY-MM-DD -> YYYYMMDD
    """
    if not date_str:
        return None
    try:
        # 如果已经是 YYYYMMDD 格式
        if len(date_str) == 8 and date_str.isdigit():
            return date_str
        # 转换 YYYY-MM-DD 格式
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y%m%d")
    except ValueError:
        return None


def update_expire_date(option_instruments):
    """
    更新 expire_date.json
    从期权合约中提取 UnderlyingInstrID 和 ExpireDate
    """
    print("\n正在更新 expire_date.json...")

    # 读取现有数据
    try:
        with open(EXPIRE_DATE_FILE, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    except FileNotFoundError:
        existing_data = {}

    # 提取新的到期日期数据
    new_expire_dates = {}
    for instrument in option_instruments:
        underlying_id = instrument.get("UnderlyingInstrID")
        expire_date = instrument.get("ExpireDate")

        if underlying_id and expire_date:
            # 转换日期格式
            formatted_date = convert_date_format(expire_date)
            if formatted_date:
                new_expire_dates[underlying_id] = formatted_date

    # 合并数据（新数据覆盖旧数据）
    merged_data = {**existing_data, **new_expire_dates}

    # 按key排序
    sorted_data = dict(sorted(merged_data.items()))

    # 保存到文件
    with open(EXPIRE_DATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, ensure_ascii=False, indent=2)

    print(f"expire_date.json 更新完成:")
    print(f"  - 原有记录: {len(existing_data)}")
    print(f"  - 新增/更新: {len(new_expire_dates)}")
    print(f"  - 合并后总计: {len(sorted_data)}")

    return sorted_data


def update_trade_para(option_instruments, futures_instruments):
    """
    更新 trade_para.json
    从期权数据提取交易参数，从期货合约数据提取保证金率
    """
    print("\n正在更新 trade_para.json...")

    # 读取现有数据
    try:
        with open(TRADE_PARA_FILE, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    except FileNotFoundError:
        existing_data = {}

    # 从期权数据提取交易参数
    option_params = {}
    for instrument in option_instruments:
        product_id = instrument.get("ProductID")
        if not product_id:
            continue

        product_id = product_id.upper()

        # 只取第一个遇到的（去重）
        if product_id not in option_params:
            option_params[product_id] = {
                "exchange_id": instrument.get("ExchangeID", ""),
                "volume_multiple": instrument.get("VolumeMultiple", 0),
                "price_tick": instrument.get("PriceTick", 0),
                "open_money_by_vol": instrument.get("CloseTodayRatioByVolume", 0),
            }

    # 从期货合约数据提取保证金率
    margin_ratios = {}
    for instrument in futures_instruments:
        product_id = instrument.get("ProductID")
        margin_ratio = instrument.get("LongMarginRatioByMoney")

        if product_id and margin_ratio is not None:
            product_id = product_id.upper()
            # 只取第一个遇到的（去重）
            if product_id not in margin_ratios:
                margin_ratios[product_id] = margin_ratio

    # 合并数据
    updated_count = 0
    new_count = 0

    for product_id, params in option_params.items():
        if product_id in existing_data:
            # 更新现有记录
            existing_data[product_id]["exchange_id"] = params["exchange_id"]
            existing_data[product_id]["volume_multiple"] = params["volume_multiple"]
            existing_data[product_id]["price_tick"] = params["price_tick"]
            existing_data[product_id]["open_money_by_vol"] = params["open_money_by_vol"]
            updated_count += 1
        else:
            # 新增记录
            existing_data[product_id] = {
                "exchange_id": params["exchange_id"],
                "volume_multiple": params["volume_multiple"],
                "price_tick": params["price_tick"],
                "open_money_by_vol": params["open_money_by_vol"],
                "margin_ratio": 0.1,  # 默认值
            }
            new_count += 1

    # 更新保证金率
    margin_updated = 0
    for futures_product_id, margin_ratio in margin_ratios.items():
        # 检查是否需要映射 (期货ProductID -> 期权ProductID)
        # IF -> IO, IM -> MO, IH -> HO
        target_product_id = PRODUCT_ID_MAPPING.get(
            futures_product_id, futures_product_id
        )

        if target_product_id in existing_data:
            existing_data[target_product_id]["margin_ratio"] = margin_ratio
            margin_updated += 1
            if futures_product_id != target_product_id:
                print(
                    f"  - 映射保证金率: {futures_product_id} -> {target_product_id}: {margin_ratio}"
                )

    # 按key排序
    sorted_data = dict(sorted(existing_data.items()))

    # 保存到文件
    with open(TRADE_PARA_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, ensure_ascii=False, indent=2)

    print(f"trade_para.json 更新完成:")
    print(f"  - 更新记录: {updated_count}")
    print(f"  - 新增记录: {new_count}")
    print(f"  - 保证金率更新: {margin_updated}")
    print(f"  - 总计: {len(sorted_data)}")

    return sorted_data


def main():
    """
    主入口函数
    """
    print("=" * 50)
    print("OpenCTP 数据维护脚本")
    print("=" * 50)

    try:
        # 1. 获取期权合约数据
        option_instruments = fetch_option_instruments()

        # 2. 获取期货合约数据（用于保证金率）
        futures_instruments = fetch_futures_instruments()

        # 3. 更新 expire_date.json
        update_expire_date(option_instruments)

        # 4. 更新 trade_para.json
        update_trade_para(option_instruments, futures_instruments)

        print("\n" + "=" * 50)
        print("所有数据维护完成!")
        print("=" * 50)

    except Exception as e:
        print(f"\n错误: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
