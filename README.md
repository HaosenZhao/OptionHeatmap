# 投资组合情景分析器

一个基于 Web 的投资组合情景分析工具，提供交互式界面来分析期权投资组合的各种风险指标。该应用程序为 `basicCal.py` 中的 `findPairScenrio` 函数提供了友好的用户界面。

## 功能特性

- **交互式参数编辑**: 修改期货 ID、投资组合构成和隐含波动率
- **用户友好的投资组合构建**: 使用表格界面轻松添加/删除期权组件
- **表格可视化**: 以交互式表格形式显示结果，支持横向和纵向滚动
- **参数存储**: 保存和加载参数集，支持自定义命名
- **实时计算**: 即时获得结果并提供视觉反馈
- **数据导出**: 将所有数据框导出为 CSV 文件并压缩为 ZIP/RAR 存档
- **响应式设计**: 支持桌面和移动设备

## 安装

1. 安装所需的包：

```bash
pip install -r requirements.txt
```

2. 确保项目目录中包含以下 JSON 数据文件：
   - `expire_date.json` - 期权到期日期数据
   - `trade_para.json` - 交易参数数据
   - `tradingDay.json` - 交易日数据

## 使用方法

1. 启动 Flask 应用程序：

```bash
python app.py
```

2. 在浏览器中访问 `http://localhost:5000`

3. 输入参数：

   - **期货 ID**: 例如 "TA601"
   - **投资组合**: 使用表格界面添加期权组件
     - 点击"Add Row"添加新行
     - 输入期权代码（如 TA601C1600）
     - 输入数量（正数为多头，负数为空头）
     - 点击"Load Sample"加载示例组合
   - **隐含波动率**: 例如 0.2

4. 点击"计算情景"按钮获取结果

5. 查看结果表格：
   - **投资组合价格**: 总投资组合价值
   - **Delta**: 对标的资产价格的敏感性
   - **Gamma**: Delta 的变化率
   - **Vega**: 对波动率变化的敏感性
   - **Theta**: 时间衰减
   - **保证金**: 所需保证金
   - **手数 Delta**: 以手数表示的 Delta

## 参数管理

### 保存参数

1. 输入参数名称
2. 点击"保存参数"按钮
3. 参数将保存到 `portfolio_parameters.json` 文件中

### 加载参数

1. 在"已保存的参数集"列表中点击参数名称
2. 参数将自动加载到表单中

### 删除参数

1. 点击参数旁边的删除按钮
2. 确认删除操作

## 数据导出

1. 计算情景后，点击"导出数据"按钮
2. 输入导出名称（例如："TA601\_分析"）
3. 点击"导出"按钮
4. 系统将创建以下文件：

   - `TA601_分析_portfolio_price.csv`
   - `TA601_分析_delta.csv`
   - `TA601_分析_gamma.csv`
   - `TA601_分析_vega.csv`
   - `TA601_分析_theta.csv`
   - `TA601_分析_margin.csv`
   - `TA601_分析_LotsDelta.csv`

5. 所有文件将压缩为 ZIP 或 RAR 存档并自动下载

## 技术说明

- 使用 Flask 作为 Web 框架
- 前端使用 Bootstrap 5 和 Font Awesome 图标
- 数据存储使用 JSON 格式，提高性能和可维护性
- 表格支持粘性标题和索引列，便于滚动查看
- 导出功能支持 ZIP 和 RAR 格式（如果系统安装了 WinRAR）
## 文件结构

```
sep_heatmap/
├── app.py                 # Flask应用程序主文件
├── basicCal.py           # 核心计算函数
├── expire_date.json      # 期权到期日期数据
├── trade_para.json       # 交易参数数据
├── tradingDay.json       # 交易日数据
├── portfolio_parameters.json  # 保存的参数集
├── requirements.txt      # Python依赖包
├── templates/
│   └── index.html       # 主页面模板
└── README.md            # 说明文档
```

## 故障排除

- **计算错误**: 确保期货 ID 和投资组合格式正确
- **导出失败**: 检查是否有足够的磁盘空间和写入权限
- **参数加载失败**: 检查 `portfolio_parameters.json` 文件格式是否正确
- **表格显示问题**: 确保浏览器支持现代 CSS 特性

## 开发说明

- 应用程序使用非交互式 matplotlib 后端，避免 Web 环境中的线程问题
- 所有计算在服务器端使用现有的 `basicCal.py` 函数执行
- 参数存储在 `portfolio_parameters.json` 中，确保持久性
- 支持中文界面和 UTF-8 编码

## 许可证

本项目仅供学习和研究使用。
