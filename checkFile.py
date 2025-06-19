import datetime as dt
import os
import commodity_common_functions as CCF
import requests
import json


def send_qiyeweixin(msg):
    webUrl = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=264136af-cce1-4606-be62-7f668edc8a7c"
    data = {"msgtype": "text", "text": {"content": msg}}
    r = requests.post(webUrl, data=(json.dumps(data, ensure_ascii=False)).encode())
    print(r.text)


def check_file(date=None):
    if date is None:
        date = dt.date.today().strftime("%Y%m%d")
    if date not in CCF.tradingDay:
        return 0
    file_path = f"E:/KurStrategy/log/option_analysis_{date}.log"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            lines = f.readlines()

            task1 = False
            task2 = False
            for line in lines:
                if "商品期权分析完成" in line:
                    task1 = True
                elif "ETF期权分析完成" in line:
                    task2 = True
    else:
        send_qiyeweixin(date + "因子生成程序未运行")
        return 1
    if task1 == True and task2 == True:
        send_qiyeweixin(date + "期货及ETF因子均已生成")
    elif task1 == True and task2 == False:
        send_qiyeweixin(date + "期货因子生成成功，ETF因子生成失败")
    elif task1 == False and task2 == True:
        send_qiyeweixin(date + "ETF因子生成成功，期货因子生成失败")
    else:
        send_qiyeweixin(date + "因子生成程序失败")
    return 0
    # if len(lines) > 100:
    #     send_qiyeweixin("文件内容过长，请检查")


def check_posfile(date=None):
    if date is None:
        date = dt.date.today().strftime("%Y%m%d")
    if date not in CCF.tradingDay:
        return 0
    file_path = f"E:/KurStrategy/log/option_analysis_{date}.log"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            lines = f.readlines()

            task1 = False
            task2 = False
            for line in lines:
                if "交易持仓分析完成" in line:
                    task1 = True
                elif "风险管理分析完成" in line:
                    task2 = True
    else:
        send_qiyeweixin(date + "持仓生成程序未运行")
        return 1
    if task1 == True and task2 == True:
        send_qiyeweixin(date + "持仓&风控生成程序成功")
    elif task1 == True and task2 == False:
        send_qiyeweixin(date + "持仓生成成功，风控生成失败")
    elif task1 == False and task2 == True:
        send_qiyeweixin(date + "持仓生成失败，风控生成成功")
    else:
        send_qiyeweixin(date + "持仓&风控生成程序失败")
    return 0


if __name__ == "__main__":
    check_file()
    check_posfile()
    # send_qiyeweixin("测试")
