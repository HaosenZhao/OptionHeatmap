import json
import os
import tempfile
import shutil
from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import basicCal
from basicCal import findPairScenrio, findInsInfo, split_instrument
import subprocess
from maintenance import (
    fetch_option_instruments,
    fetch_futures_instruments,
    update_expire_date,
    update_trade_para,
)

app = Flask(__name__)

# Configuration
PARAMETERS_FILE = "portfolio_parameters.json"


def reload_config():
    """重新加载配置文件到 basicCal 模块"""
    with open("expire_date.json", "r", encoding="utf-8") as f:
        basicCal.expiredate = json.load(f)
    with open("trade_para.json", "r", encoding="utf-8") as f:
        basicCal.trade_para = json.load(f)
    print("配置文件已重新加载")


def load_parameters():
    """Load saved parameters from JSON file"""
    if os.path.exists(PARAMETERS_FILE):
        with open(PARAMETERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_parameters(parameters):
    """Save parameters to JSON file"""
    with open(PARAMETERS_FILE, "w", encoding="utf-8") as f:
        json.dump(parameters, f, ensure_ascii=False, indent=2)


def format_dataframe_for_table(df, decimals=2):
    """Format dataframe for HTML table display"""
    df_formatted = df.round(decimals)

    # Convert to HTML table with styling
    html_table = df_formatted.to_html(
        classes="table table-striped table-hover table-sm",
        table_id=None,
        escape=False,
        index=True,
        header=True,
    )

    return html_table


@app.route("/")
def index():
    """Main page"""
    return render_template("index.html")


@app.route("/calculate", methods=["POST"])
def calculate():
    """Calculate portfolio scenario and return heatmaps"""
    try:
        data = request.get_json()

        future_id = data.get("future_id", "FG605")
        portfolio = data.get("portfolio", {"FG605C1120": 1, "FG605C1200": -2})
        iv = float(data.get("iv", 0.4))
        iv_map = {k: float(v) for k, v in data.get("iv_map", {}).items()}
        cost = float(data.get("cost", 0))

        # Validate portfolio format
        if not isinstance(portfolio, dict):
            return jsonify({"error": "Portfolio must be a valid object"}), 400
        for opt_code in portfolio:
            try:
                split_instrument(opt_code)
            except ValueError as e:
                return (
                    jsonify({"error": f'Invalid option code "{opt_code}": {str(e)}'}),
                    400,
                )

        # Calculate scenario
        result = findPairScenrio(future_id, portfolio, iv, cost, iv_map=iv_map)

        # Format dataframes for table display
        tables = {}
        for key, df in result.items():
            tables[key] = format_dataframe_for_table(df, decimals=4 if key == "gamma" else 2)

        return jsonify(
            {"success": True, "tables": tables, "data_keys": list(result.keys())}
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/save_parameters", methods=["POST"])
def save_params():
    """Save current parameters with a name"""
    try:
        data = request.get_json()
        name = data.get("name")
        parameters = data.get("parameters")

        if not name or not parameters:
            return jsonify({"error": "Name and parameters are required"}), 400

        # Load existing parameters
        all_params = load_parameters()
        all_params[name] = parameters

        # Save to file
        save_parameters(all_params)

        return jsonify({"success": True, "message": f'Parameters saved as "{name}"'})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/load_parameters", methods=["GET"])
def load_params():
    """Load all saved parameters"""
    try:
        parameters = load_parameters()
        return jsonify({"success": True, "parameters": parameters})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/delete_parameters", methods=["POST"])
def delete_params():
    """Delete saved parameters by name"""
    try:
        data = request.get_json()
        name = data.get("name")

        if not name:
            return jsonify({"error": "Name is required"}), 400

        # Load existing parameters
        all_params = load_parameters()

        if name in all_params:
            del all_params[name]
            save_parameters(all_params)
            return jsonify({"success": True, "message": f'Parameters "{name}" deleted'})
        else:
            return jsonify({"error": f'Parameters "{name}" not found'}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/export", methods=["POST"])
def export_data():
    """Export all dataframes as CSV files and compress them into a RAR archive"""
    try:
        data = request.get_json()
        future_id = data.get("future_id", "").strip()
        iv = float(data.get("iv", 0.2))
        iv_map = {k: float(v) for k, v in data.get("iv_map", {}).items()}
        cost = float(data.get("cost", 0))
        export_name = data.get("export_name", "").strip()

        if not export_name:
            return jsonify({"success": False, "error": "Export name is required"})

        if not future_id:
            return jsonify({"success": False, "error": "Future ID is required"})

        # Portfolio is already a dict from the frontend
        portfolio = data.get("portfolio", {})
        if not isinstance(portfolio, dict):
            return jsonify({"success": False, "error": "Invalid portfolio format"})

        # Calculate scenario
        result = findPairScenrio(future_id, portfolio, iv, cost, iv_map=iv_map)

        # Create temporary directory for CSV files
        temp_dir = tempfile.mkdtemp()

        try:
            # Export each dataframe as CSV
            csv_files = []
            for key, df in result.items():
                csv_filename = f"{export_name}_{key}.csv"
                csv_path = os.path.join(temp_dir, csv_filename)
                df.to_csv(csv_path, encoding="utf-8-sig")
                csv_files.append(csv_path)

            # Try to create RAR archive first, fallback to ZIP
            rar_filename = f"{export_name}.rar"
            rar_path = os.path.join(os.getcwd(), rar_filename)

            # Check if RAR is available
            rar_available = False
            try:
                # Try to find RAR executable
                result = subprocess.run(
                    ["rar"], check=True, capture_output=True, text=True
                )
                rar_available = True
                print("RAR executable found")
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(f"RAR not found: {e}")
                try:
                    # Try WinRAR
                    result = subprocess.run(
                        ["winrar"], check=True, capture_output=True, text=True
                    )
                    rar_available = True
                    print("WinRAR executable found")
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    print(f"WinRAR not found: {e}")
                    pass

            if rar_available:
                # Create RAR archive
                cmd = ["rar", "a", "-ep1", rar_path] + csv_files
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    return jsonify(
                        {
                            "success": True,
                            "message": f"Data exported successfully as {rar_filename}",
                            "download_url": f"/download/{rar_filename}",
                        }
                    )
                except subprocess.CalledProcessError:
                    # Fallback to ZIP if RAR creation fails
                    pass

            # Create ZIP file (fallback or primary method)
            import zipfile

            zip_filename = f"{export_name}.zip"
            zip_path = os.path.join(os.getcwd(), zip_filename)

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for csv_file in csv_files:
                    filename = os.path.basename(csv_file)
                    zipf.write(csv_file, filename)

            return jsonify(
                {
                    "success": True,
                    "message": f"Data exported successfully as {zip_filename}",
                    "download_url": f"/download/{zip_filename}",
                }
            )

        finally:
            # Clean up temporary directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/download/<filename>")
def download_file(filename):
    """Download exported files"""
    try:
        file_path = os.path.join(os.getcwd(), filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({"success": False, "error": "File not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/update_instruments", methods=["POST"])
def update_instruments():
    """从 OpenCTP API 更新合约数据"""
    try:
        # 1. 获取期权合约数据
        option_instruments = fetch_option_instruments()

        # 2. 获取期货合约数据（用于保证金率）
        futures_instruments = fetch_futures_instruments()

        # 3. 更新 expire_date.json
        expire_result = update_expire_date(option_instruments)

        # 4. 更新 trade_para.json
        trade_result = update_trade_para(option_instruments, futures_instruments)

        # 5. 重新加载配置
        reload_config()

        return jsonify(
            {
                "success": True,
                "message": "合约数据更新成功",
                "details": {
                    "expire_date_count": len(expire_result),
                    "trade_para_count": len(trade_result),
                    "option_instruments": len(option_instruments),
                    "futures_instruments": len(futures_instruments),
                },
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
