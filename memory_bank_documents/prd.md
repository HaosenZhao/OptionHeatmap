阅读当前项目代码，增加新功能，写在maintenance.py中，对 @expire_date.json 和 @trade_para.json 进行维护
你需要首先阅读这两个json，了解其字段
1. 通过 http://dict.openctp.cn/instruments?types=option ，返回
{
  "rsp_code": 0,
  "rsp_message": "succeed",
  "data": [
    {
      "ExchangeID": "CFFEX",
      "InstrumentID": "IF2601",
      "InstrumentName": "股指2601",
      "ProductClass": "1",
      "ProductID": "IF",
      "VolumeMultiple": 300,
      "PriceTick": 0.2,
      "LongMarginRatioByMoney": 0.12,
      "ShortMarginRatioByMoney": 0.12,
      "LongMarginRatioByVolume": 0,
      "ShortMarginRatioByVolume": 0,
      "OpenRatioByMoney": 0.0000238,
      "OpenRatioByVolume": 0.01,
      "CloseRatioByMoney": 0.0000238,
      "CloseRatioByVolume": 0.01,
      "CloseTodayRatioByMoney": 0.0002308,
      "CloseTodayRatioByVolume": 0.01,
      "DeliveryYear": 2026,
      "DeliveryMonth": 1,
      "OpenDate": "2025-11-24",
      "ExpireDate": "2026-01-16",
      "DeliveryDate": "2026-01-16",
      "UnderlyingInstrID": "IF",
      "UnderlyingMultiple": 1,
      "OptionsType": "",
      "StrikePrice": null,
      "InstLifePhase": "1"
    },
选择 unique InstrumentID的ExpireDate，按照之前的格式更新 @expire_date.json

2. 通过 http://dict.openctp.cn/instruments?types=option
选择 unique ProductID，VolumeMultiple，PriceTick，CloseTodayRatioByVolume, 更新到trade_para
再通过 http://dict.openctp.cn/instruments
返回 
{
  "rsp_code": 0,
  "rsp_message": "succeed",
  "data": [
    {
      "ExchangeID": "CFFEX",
      "InstrumentID": "IF2601",
      "InstrumentName": "股指2601",
      "ProductClass": "1",
      "ProductID": "IF",
      "VolumeMultiple": 300,
      "PriceTick": 0.2,
      "LongMarginRatioByMoney": 0.12,
      "ShortMarginRatioByMoney": 0.12,
      "LongMarginRatioByVolume": 0,
      "ShortMarginRatioByVolume": 0,
      "OpenRatioByMoney": 0.0000238,
      "OpenRatioByVolume": 0.01,
      "CloseRatioByMoney": 0.0000238,
      "CloseRatioByVolume": 0.01,
      "CloseTodayRatioByMoney": 0.0002308,
      "CloseTodayRatioByVolume": 0.01,
      "DeliveryYear": 2026,
      "DeliveryMonth": 1,
      "OpenDate": "2025-11-24",
      "ExpireDate": "2026-01-16",
      "DeliveryDate": "2026-01-16",
      "UnderlyingInstrID": "IF",
      "UnderlyingMultiple": 1,
      "OptionsType": "",
      "StrikePrice": null,
      "InstLifePhase": "1"
    },
找到每一个ProductID的LongMarginRatioByMoney 更新到 trade_para的margin_ratio

分布测试维护代码，确保运行