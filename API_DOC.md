# Portfolio Scenario Analyzer API 文档

## 概述

本文档描述了 Portfolio Scenario Analyzer 系统的所有 API 端点。

**Base URL**: `http://localhost:8080`

---

## 目录

1. [页面路由](#页面路由)
2. [计算 API](#计算-api)
3. [参数管理 API](#参数管理-api)
4. [数据导出 API](#数据导出-api)
5. [数据维护 API](#数据维护-api)

---

## 页面路由

### GET /

**描述**: 返回主页面

**响应**: HTML 页面

**示例**:
```bash
curl http://localhost:8080/
```

---

## 计算 API

### POST /calculate

**描述**: 计算投资组合情景分析，返回各种风险指标的热力图数据

**请求头**:
```
Content-Type: application/json
```

**请求体参数**:

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| future_id | string | 是 | "TA601" | 期货合约ID，如 "TA601", "IO2509" |
| portfolio | object | 是 | {} | 投资组合，键为期权代码，值为持仓数量 |
| iv | number | 是 | 0.2 | 隐含波动率 (0-2) |
| cost | number | 否 | 0 | 初始成本/权利金 |

**请求示例**:
```bash
curl -X POST http://localhost:8080/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "future_id": "TA601",
    "portfolio": {
      "TA601C1600": 1,
      "TA601P1800": -1
    },
    "iv": 0.2,
    "cost": 100
  }'
```

**成功响应** (200):
```json
{
  "success": true,
  "tables": {
    "portfolio_price": "<html table>",
    "delta": "<html table>",
    "gamma": "<html table>",
    "vega": "<html table>",
    "theta": "<html table>",
    "margin": "<html table>",
    "LotsDelta": "<html table>",
    "portfolio_price_afterfee": "<html table>",
    "pnl": "<html table>",
    "pnl_afterfee": "<html table>"
  },
  "data_keys": ["portfolio_price", "delta", "gamma", "vega", "theta", "margin", "LotsDelta", "portfolio_price_afterfee", "pnl", "pnl_afterfee"]
}
```

**错误响应** (400/500):
```json
{
  "error": "错误信息"
}
```

**返回数据说明**:
- `portfolio_price`: 投资组合价格
- `delta`: Delta 值
- `gamma`: Gamma 值
- `vega`: Vega 值
- `theta`: Theta 值
- `margin`: 保证金
- `LotsDelta`: 手数 Delta
- `portfolio_price_afterfee`: 扣除手续费后的组合价格
- `pnl`: 盈亏
- `pnl_afterfee`: 扣除手续费后的盈亏

---

## 参数管理 API

### POST /save_parameters

**描述**: 保存当前参数集

**请求头**:
```
Content-Type: application/json
```

**请求体参数**:

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| name | string | 是 | 参数集名称 |
| parameters | object | 是 | 参数对象 |

**请求示例**:
```bash
curl -X POST http://localhost:8080/save_parameters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "我的策略1",
    "parameters": {
      "future_id": "TA601",
      "portfolio": {
        "TA601C1600": 1,
        "TA601P1800": -1
      },
      "iv": 0.2,
      "cost": 0
    }
  }'
```

**成功响应** (200):
```json
{
  "success": true,
  "message": "Parameters saved as \"我的策略1\""
}
```

**错误响应** (400/500):
```json
{
  "error": "Name and parameters are required"
}
```

---

### GET /load_parameters

**描述**: 加载所有已保存的参数集

**请求示例**:
```bash
curl http://localhost:8080/load_parameters
```

**成功响应** (200):
```json
{
  "success": true,
  "parameters": {
    "我的策略1": {
      "future_id": "TA601",
      "portfolio": {
        "TA601C1600": 1,
        "TA601P1800": -1
      },
      "iv": 0.2,
      "cost": 0
    },
    "我的策略2": {
      "future_id": "IO2509",
      "portfolio": {
        "IO2509C4000": 1
      },
      "iv": 0.15,
      "cost": 500
    }
  }
}
```

---

### POST /delete_parameters

**描述**: 删除指定名称的参数集

**请求头**:
```
Content-Type: application/json
```

**请求体参数**:

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| name | string | 是 | 要删除的参数集名称 |

**请求示例**:
```bash
curl -X POST http://localhost:8080/delete_parameters \
  -H "Content-Type: application/json" \
  -d '{"name": "我的策略1"}'
```

**成功响应** (200):
```json
{
  "success": true,
  "message": "Parameters \"我的策略1\" deleted"
}
```

**错误响应** (404):
```json
{
  "error": "Parameters \"我的策略1\" not found"
}
```

---

## 数据导出 API

### POST /export

**描述**: 导出计算结果为 CSV 文件，并打包为 ZIP/RAR 压缩包

**请求头**:
```
Content-Type: application/json
```

**请求体参数**:

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| future_id | string | 是 | 期货合约ID |
| portfolio | object | 是 | 投资组合 |
| iv | number | 是 | 隐含波动率 |
| cost | number | 否 | 初始成本 |
| export_name | string | 是 | 导出文件名前缀 |

**请求示例**:
```bash
curl -X POST http://localhost:8080/export \
  -H "Content-Type: application/json" \
  -d '{
    "future_id": "TA601",
    "portfolio": {
      "TA601C1600": 1,
      "TA601P1800": -1
    },
    "iv": 0.2,
    "cost": 0,
    "export_name": "TA601_分析"
  }'
```

**成功响应** (200):
```json
{
  "success": true,
  "message": "Data exported successfully as TA601_分析.zip",
  "download_url": "/download/TA601_分析.zip"
}
```

**导出文件列表**:
- `{export_name}_portfolio_price.csv`
- `{export_name}_delta.csv`
- `{export_name}_gamma.csv`
- `{export_name}_vega.csv`
- `{export_name}_theta.csv`
- `{export_name}_margin.csv`
- `{export_name}_LotsDelta.csv`
- `{export_name}_portfolio_price_afterfee.csv`
- `{export_name}_pnl.csv`
- `{export_name}_pnl_afterfee.csv`

---

### GET /download/{filename}

**描述**: 下载导出的文件

**路径参数**:

| 参数 | 类型 | 描述 |
|------|------|------|
| filename | string | 文件名 |

**请求示例**:
```bash
curl -O http://localhost:8080/download/TA601_分析.zip
```

**成功响应**: 文件下载

**错误响应** (404):
```json
{
  "success": false,
  "error": "File not found"
}
```

---

## 数据维护 API

### POST /update_instruments

**描述**: 从 OpenCTP API 更新合约数据，包括到期日期和交易参数

**数据来源**:
- 期权数据: `http://dict.openctp.cn/instruments?types=option`
- 期货数据: `http://dict.openctp.cn/instruments?types=futures`

**请求示例**:
```bash
curl -X POST http://localhost:8080/update_instruments \
  -H "Content-Type: application/json"
```

**成功响应** (200):
```json
{
  "success": true,
  "message": "合约数据更新成功",
  "details": {
    "expire_date_count": 579,
    "trade_para_count": 144,
    "option_instruments": 22690,
    "futures_instruments": 862
  }
}
```

**响应字段说明**:
- `expire_date_count`: 更新后的到期日期记录数
- `trade_para_count`: 更新后的交易参数记录数
- `option_instruments`: 获取的期权合约数量
- `futures_instruments`: 获取的期货合约数量

**更新内容**:
1. `expire_date.json` - 期权合约到期日期
2. `trade_para.json` - 交易参数（合约乘数、最小变动价位、手续费、保证金率）

**特殊映射** (股指期货 → 股指期权):
- IF → IO (沪深300)
- IM → MO (中证1000)
- IH → HO (上证50)

**错误响应** (500):
```json
{
  "success": false,
  "error": "获取期权数据失败: Connection timeout"
}
```

---

## 错误码说明

| HTTP 状态码 | 说明 |
|-------------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源未找到 |
| 500 | 服务器内部错误 |

---

## 数据格式说明

### 期权代码格式

期权代码格式为: `{ProductID}{YYMM}{C/P}{Strike}`

示例:
- `TA601C1600` - TA2601 看涨期权，行权价 1600
- `IO2509P4000` - IO2509 看跌期权，行权价 4000
- `m2601C3200` - 豆粕2601 看涨期权，行权价 3200

### 投资组合格式

```json
{
  "期权代码1": 数量1,
  "期权代码2": 数量2
}
```

- 正数表示多头（买入）
- 负数表示空头（卖出）

示例:
```json
{
  "TA601C1600": 1,    // 买入1手看涨期权
  "TA601P1800": -1    // 卖出1手看跌期权
}
```

---

## 使用示例

### 完整工作流程

```bash
# 1. 更新合约数据
curl -X POST http://localhost:8080/update_instruments

# 2. 计算情景
curl -X POST http://localhost:8080/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "future_id": "TA601",
    "portfolio": {"TA601C1600": 1, "TA601P1800": -1},
    "iv": 0.2,
    "cost": 0
  }'

# 3. 保存参数
curl -X POST http://localhost:8080/save_parameters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "我的策略",
    "parameters": {
      "future_id": "TA601",
      "portfolio": {"TA601C1600": 1, "TA601P1800": -1},
      "iv": 0.2,
      "cost": 0
    }
  }'

# 4. 导出数据
curl -X POST http://localhost:8080/export \
  -H "Content-Type: application/json" \
  -d '{
    "future_id": "TA601",
    "portfolio": {"TA601C1600": 1, "TA601P1800": -1},
    "iv": 0.2,
    "cost": 0,
    "export_name": "TA601_策略分析"
  }'

# 5. 下载文件
curl -O http://localhost:8080/download/TA601_策略分析.zip
```

---

## 配置文件

| 文件 | 说明 |
|------|------|
| `expire_date.json` | 期权到期日期配置 |
| `trade_para.json` | 交易参数配置（乘数、价格跳动、手续费、保证金率） |
| `tradingDay.json` | 交易日历 |
| `portfolio_parameters.json` | 用户保存的参数集 |

---

## 注意事项

1. **更新合约数据**: 建议每日开盘前执行一次 `/update_instruments`
2. **网络超时**: 更新合约数据时可能需要 30 秒左右，请耐心等待
3. **期权代码**: 确保期权代码与期货ID匹配（如 `TA601C1600` 对应 `TA601`）
4. **隐含波动率**: 通常在 0.1-0.5 之间，最大不超过 2
