import pandas as pd
import numpy as np
import commodity_common_functions as CCF
import datetime as dt
import seaborn as sns
from flask import Flask, render_template_string, request
from jinja2 import Template

# from WindPy import w
# w.start()

############ 寻找underlying相同的期权合约的信息,输入为underlying_id
infodict = {}


def findInsInfo(code):
    if code in infodict:
        return infodict[code]
    SQL_cmd = f"""SELECT 
        i.exchange_id,
        i.expiredate,
        i.volume_multiple,
        i.price_tick,
        icr.open_money_by_vol
    FROM 
        instrument i
    LEFT JOIN 
        commission_info icr
    ON 
        i.instrument_id = icr.instrument_id
    WHERE 
        i.underlying_instr_id = '{code}'
    LIMIT 1
        """
    info = pd.read_sql(sql=SQL_cmd, con=CCF.market_base)
    info = info.fillna(0)
    info = info.to_dict("records")[0]
    if info["exchange_id"] == "CFFEX":
        info["exchange_id"] = "CFE"
    elif info["exchange_id"] == "SHFE":
        info["exchange_id"] = "SHF"
    elif info["exchange_id"] == "CZCE":
        info["exchange_id"] = "CZC"
    elif info["exchange_id"] == "GFEX":
        info["exchange_id"] = "GFE"

    SQL_cmd = f"""SELECT 
        long_margin_ratio
    FROM 
        instrument 
    WHERE 
        instrument_id = '{code}'
        """
    info2 = pd.read_sql(sql=SQL_cmd, con=CCF.market_base)
    info2 = info2.to_dict("records")[0]
    info["margin_ratio"] = info2["long_margin_ratio"]
    infodict[code] = info
    return info


def findPortfolioDetails(future_id, portfolio, s, ttm, iv):
    t = ttm / 243
    info = findInsInfo(future_id)
    portfolio_price = 0
    delta = 0
    gamma = 0
    vega = 0
    theta = 0
    margin = 0
    for opt_code in portfolio:
        k = float(opt_code[:-1])
        typ = opt_code[-1]
        num_hold = portfolio[opt_code]
        optprice = (
            CCF.BSMiv.black_scholes_merton(typ, s, k, t, 0, iv, 0)
            * info["volume_multiple"]
            * num_hold
        )
        portfolio_price += optprice
        delta += (
            CCF.BSMgreeks.delta(typ, s, k, t, 0, iv, 0)
            * info["volume_multiple"]
            * num_hold
        )
        gamma += (
            CCF.BSMgreeks.gamma(typ, s, k, t, 0, iv, 0)
            * info["volume_multiple"]
            * num_hold
        )
        vega += (
            CCF.BSMgreeks.vega(typ, s, k, t, 0, iv, 0)
            * info["volume_multiple"]
            * num_hold
        )
        theta += (
            CCF.BSMgreeks.theta(typ, s, k, t, 0, iv, 0)
            * info["volume_multiple"]
            * num_hold
        )
        if num_hold < 0:
            margin -= (
                s * num_hold * info["margin_ratio"] * info["volume_multiple"] / 2
                + optprice
            )
    return [portfolio_price, delta, gamma, vega, theta, margin]


def findPairScenrio(future_id, opt_typ, shortk, longk, n, iv):
    portfolio = {f"{shortk}{opt_typ}": -1 * n, f"{longk}{opt_typ}": 1}
    optinfo = findInsInfo(future_id)
    today = dt.date.today().strftime(format="%Y%m%d")
    maxttm = len(
        CCF.tradingDay[
            (CCF.tradingDay <= optinfo["expiredate"]) & (CCF.tradingDay >= today)
        ]
    )
    if n == 1:
        print("Long Gamma Strategy")
    else:
        if opt_typ == "c" and shortk > longk:
            print("Short Gamma Strategy")
        elif opt_typ == "p" and shortk < longk:
            print("Short Gamma Strategy")
        else:
            print("Long Gamma Strategy")
    multi = optinfo["volume_multiple"]
    bidp = optinfo["price_tick"]
    askp = bidp * 2
    commission = optinfo["open_money_by_vol"]
    exchange = optinfo["exchange_id"]
    margin_ratio = optinfo["margin_ratio"] / 2
    initport_price = (n + 1) * 2 * commission + (askp - bidp * n) * multi
    margin_prepared = shortk * multi * n * margin_ratio

    maxs = max(shortk, longk) * 1.2
    lows = min(shortk, longk) * 0.8
    index = np.round(np.linspace(lows, maxs, 30), 1)
    columns = list(range(1, maxttm + 1))
    keys = ["portfolio_price", "delta", "gamma", "vega", "theta", "margin"]
    dataframe_dict = {}
    for key in keys:
        df = pd.DataFrame(0, index=index, columns=columns)
        dataframe_dict[key] = df
    for s in index:
        for ttm in columns:
            portfolio_price, delta, gamma, vega, theta, margin = findPortfolioDetails(
                future_id, portfolio, s, ttm, iv
            )
            dataframe_dict["portfolio_price"].loc[s, ttm] = portfolio_price
            dataframe_dict["delta"].loc[s, ttm] = delta
            dataframe_dict["gamma"].loc[s, ttm] = gamma
            dataframe_dict["vega"].loc[s, ttm] = vega
            dataframe_dict["theta"].loc[s, ttm] = theta
            dataframe_dict["margin"].loc[s, ttm] = margin
    dataframe_dict["PNL"] = dataframe_dict["portfolio_price"] - initport_price
    dataframe_dict["LotsDelta"] = dataframe_dict["delta"] / multi
    dataframe_dict["AnnualRet"] = (
        dataframe_dict["PNL"] / margin_prepared * 243 / maxttm * 100
    )
    for key in dataframe_dict:
        dataframe_dict[key] = np.round(dataframe_dict[key], 2)
    return dataframe_dict


def transferToHTML(future_id, opt_typ, shortk, longk, n, iv):
    dataframe_dict = findPairScenrio(future_id, opt_typ, shortk, longk, n, iv)
    # 创建一个空列表来存储每个 DataFrame 的样式化 HTML 内容
    keys = list(dataframe_dict.keys())
    # 创建一个空列表来存储每个 DataFrame 的样式化 HTML 内容
    styled_dfs_html = []
    for key, df in dataframe_dict.items():
        cm = sns.color_palette("rocket", as_cmap=True)
        styled_df = df.style.background_gradient(cmap=cm).format(precision=2)
        styled_dfs_html.append(styled_df.to_html())

    # 在 Python 中进行 zip 操作
    zipped_data = list(zip(keys, styled_dfs_html))

    # 生成 HTML 模板，添加固定表格大小的 CSS 样式
    html_template = """
    <!DOCTYPE html>
    <html lang="en">

    <head>
        <meta charset="UTF-8">
        <title>DataFrames</title>
        <style>
           .tabcontent {
                display: none;
            }
            table {
                width: 80%; /* 可以根据需要调整表格宽度 */
                table-layout: fixed; /* 固定表格布局，使单元格宽度均匀分配 */
                border-collapse: collapse;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: center;
                overflow: hidden; /* 防止内容溢出 */
                text-overflow: ellipsis; /* 溢出内容显示省略号 */
                white-space: nowrap; /* 不换行 */
            }
        </style>
    </head>

    <body>

        <!-- 选项卡按钮 -->
        <div>
            {% for key in keys %}
            <button class="tablinks" onclick="openCity(event, '{{ key }}')">{{ key }}</button>
            {% endfor %}
        </div>

        <!-- 选项卡内容 -->
        {% for key, html_content in zipped_data %}
        <div id="{{ key }}" class="tabcontent">
            {{ html_content|safe }}
        </div>
        {% endfor %}

        <script>
            function openCity(evt, cityName) {
                var i, tabcontent, tablinks;
                tabcontent = document.getElementsByClassName("tabcontent");
                for (i = 0; i < tabcontent.length; i++) {
                    tabcontent[i].style.display = "none";
                }
                tablinks = document.getElementsByClassName("tablinks");
                for (i = 0; i < tablinks.length; i++) {
                    tablinks[i].className = tablinks[i].className.replace(" active", "");
                }
                document.getElementById(cityName).style.display = "block";
                evt.currentTarget.className += " active";
            }

            // 显示第一个选项卡
            document.getElementById('{{ keys[0] }}').style.display = "block";
            document.getElementsByClassName('tablinks')[0].className += " active";
        </script>

    </body>

    </html>
    """

    # 使用 Jinja2 模板引擎来填充数据
    template = Template(html_template)
    filled_html = template.render(keys=keys, zipped_data=zipped_data)

    # 将生成的 HTML 保存到文件
    with open("./combined_dataframes.html", "w", encoding="utf-8") as f:
        f.write(filled_html)
    return 0


####################fdsadasdasdad##############################


app = Flask(__name__)
# 生成 HTML 模板
html_template = """
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <title>DataFrames</title>
    <style>
       .tabcontent {
            display: none;
        }
        table {
            width: 100%;
            table-layout: fixed;
            border-collapse: collapse;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: center;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
    </style>
</head>

<body>
    <label for="future_id">输入 future_id: </label>
    <input type="text" id="future_id" value="{{ future_id }}">
    <label for="opt_typ">输入 opt_typ: </label>
    <input type="text" id="opt_typ" value="{{ opt_typ }}">
    <label for="shortk">输入 shortk: </label>
    <input type="number" id="shortk" value="{{ shortk }}">
    <label for="longk">输入 longk: </label>
    <input type="number" id="longk" value="{{ longk }}">
    <label for="n">输入 n: </label>
    <input type="number" id="n" value="{{ n }}">
    <label for="iv">输入 iv: </label>
    <input type="number" id="iv" value="{{ iv }}">
    <button onclick="updateTables()">更新表格</button>

    <!-- tab-buttons -->
    <div id="tab-buttons">
        {% for key in keys %}
        <button class="tablinks" onclick="openCity(event, '{{ key }}')">{{ key }}</button>
        {% endfor %}
    </div>
    <!-- /tab-buttons -->

    <!-- tab-contents -->
    <div id="tab-contents">
        {% for key, html_content in zipped_data %}
        <div id="{{ key }}" class="tabcontent">
            {{ html_content|safe }}
        </div>
        {% endfor %}
    </div>
    <!-- /tab-contents -->

    <script>
        function openCity(evt, cityName) {
            var i, tabcontent, tablinks;
            tabcontent = document.getElementsByClassName("tabcontent");
            for (i = 0; i < tabcontent.length; i++) {
                tabcontent[i].style.display = "none";
            }
            tablinks = document.getElementsByClassName("tablinks");
            for (i = 0; i < tablinks.length; i++) {
                tablinks[i].className = tablinks[i].className.replace(" active", "");
            }
            document.getElementById(cityName).style.display = "block";
            evt.currentTarget.className += " active";
        }

        function updateTables() {
            var future_id = document.getElementById('future_id').value;
            var opt_typ = document.getElementById('opt_typ').value;
            var shortk = document.getElementById('shortk').value;
            var longk = document.getElementById('longk').value;
            var n = document.getElementById('n').value;
            var iv = document.getElementById('iv').value;
            var url = '/update?future_id=' + future_id + '&opt_typ=' + opt_typ + '&shortk=' + shortk + '&longk=' + longk + '&n=' + n + '&iv=' + iv;
            fetch(url)
              .then(response => response.text())
              .then(data => {
                    var startButtons = data.indexOf('<!-- tab-buttons -->');
                    var endButtons = data.indexOf('<!-- /tab-buttons -->');
                    var startContents = data.indexOf('<!-- tab-contents -->');
                    var endContents = data.indexOf('<!-- /tab-contents -->');
                    if (startButtons!== -1 && endButtons!== -1) {
                        document.getElementById('tab-buttons').innerHTML = data.slice(startButtons + '<!-- tab-buttons -->'.length, endButtons);
                    }
                    if (startContents!== -1 && endContents!== -1) {
                        document.getElementById('tab-contents').innerHTML = data.slice(startContents + '<!-- tab-contents -->'.length, endContents);
                    }
                    // 显示第一个选项卡
                    document.getElementById('{{ keys[0] }}').style.display = "block";
                    document.getElementsByClassName('tablinks')[0].className += " active";
                });
        }

        // 显示第一个选项卡
        document.getElementById('{{ keys[0] }}').style.display = "block";
        document.getElementsByClassName('tablinks')[0].className += " active";
    </script>
</body>

</html>
"""


@app.route("/")
def index():
    future_id = "FG505"
    opt_typ = "c"
    shortk = 1820
    longk = 1620
    n = 6
    iv = 0.9
    dataframe_dict = findPairScenrio(future_id, opt_typ, shortk, longk, n, iv)
    styled_dfs_html = []
    for key, df in dataframe_dict.items():
        cm = sns.color_palette("rocket", as_cmap=True)
        styled_df = df.style.background_gradient(cmap=cm).format(precision=2)
        styled_dfs_html.append(styled_df.to_html())
    zipped_data = list(zip(dataframe_dict.keys(), styled_dfs_html))
    template = Template(html_template)
    filled_html = template.render(
        future_id=future_id,
        opt_typ=opt_typ,
        shortk=shortk,
        longk=longk,
        n=n,
        iv=iv,
        keys=dataframe_dict.keys(),
        zipped_data=zipped_data,
    )
    return filled_html


@app.route("/update")
def update():
    future_id = request.args.get("future_id")
    opt_typ = request.args.get("opt_typ")
    shortk = int(request.args.get("shortk"))
    longk = int(request.args.get("longk"))
    n = int(request.args.get("n"))
    iv = float(request.args.get("iv"))
    dataframe_dict = findPairScenrio(future_id, opt_typ, shortk, longk, n, iv)
    styled_dfs_html = []
    for key, df in dataframe_dict.items():
        cm = sns.color_palette("rocket", as_cmap=True)
        styled_df = df.style.background_gradient(cmap=cm).format(precision=2)
        styled_dfs_html.append(styled_df.to_html())
    zipped_data = list(zip(dataframe_dict.keys(), styled_dfs_html))
    template = Template(html_template)
    filled_html = template.render(
        future_id=future_id,
        opt_typ=opt_typ,
        shortk=shortk,
        longk=longk,
        n=n,
        iv=iv,
        keys=dataframe_dict.keys(),
        zipped_data=zipped_data,
    )
    return filled_html


if __name__ == "__main__":
    app.run(debug=True)
