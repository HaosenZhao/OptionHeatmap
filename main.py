from pdb import run
import OptionRiskMetrix as ORMcommodity
import OptionRiskMetrixETF as ORMetf
import datetime as dt
import logging
import traceback
import BalanceIncomeStatement
import RiskManagementSystem


def run_analysis_factor(date=None):
    """
    运行商品期权和ETF期权分析

    Args:
        date: 分析日期，格式为YYYYMMDD，默认为当天
    """
    if date is None:
        date = dt.date.today().strftime("%Y%m%d")

    logging.basicConfig(
        filename=f"E:/KurStrategy/log/option_analysis_{date}.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logging.info("开始分析交易持仓...")

    try:
        logging.info("开始分析商品期权...")
        ORMcommodity.main(date)
        logging.info("商品期权分析完成")
    except Exception as e:
        logging.error(f"商品期权分析失败: {str(e)}")
        logging.error(traceback.format_exc())

    try:
        logging.info("开始分析ETF期权...")
        ORMetf.main(date)
        logging.info("ETF期权分析完成")
    except Exception as e:
        logging.error(f"ETF期权分析失败: {str(e)}")
        logging.error(traceback.format_exc())


def run_analysis_portfolio(date=None):
    """
    运行商品期权和ETF期权分析

    Args:
        date: 分析日期，格式为YYYYMMDD，默认为当天
    """
    if date is None:
        date = dt.date.today().strftime("%Y%m%d")

    logging.basicConfig(
        filename=f"E:/KurStrategy/log/option_analysis_{date}.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    try:
        logging.info("开始分析交易持仓...")
        BalanceIncomeStatement.main(date)
        logging.info("交易持仓分析完成")
    except Exception as e:
        logging.error(f"交易持仓分析失败: {str(e)}")
        logging.error(traceback.format_exc())

    try:
        logging.info("开始分析风险管理...")
        RiskManagementSystem.main(date)
        logging.info("风险管理分析完成")
    except Exception as e:
        logging.error(f"风险管理分析失败: {str(e)}")
        logging.error(traceback.format_exc())


if __name__ == "__main__":
    run_analysis_factor()
    run_analysis_portfolio()
    # ORMcommodity.main()
    # ORMcommodity.getPayoffSeries()
