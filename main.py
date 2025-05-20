import OptionRiskMetrix as ORMcommodity
import OptionRiskMetrixETF as ORMetf
import datetime as dt
import logging
import traceback


def run_analysis(date=None):
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


if __name__ == "__main__":
    run_analysis()
    # ORMcommodity.main()
    # ORMcommodity.getPayoffSeries()
