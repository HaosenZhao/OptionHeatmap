# Project Brief: Portfolio Scenario Table Analyzer

## Project Overview
A web-based portfolio scenario analysis tool that provides an interactive interface for analyzing various risk metrics of option portfolios. The application provides a user-friendly interface for the `findPairScenrio` function in `basicCal.py`.

## Core Functionality
- **Interactive Parameter Editing**: Modify futures ID, portfolio composition, and implied volatility
- **User-friendly Portfolio Building**: Use table interface to easily add/remove option components
- **Table Visualization**: Display results in interactive tables with horizontal and vertical scrolling
- **Parameter Storage**: Save and load parameter sets with custom naming
- **Real-time Calculation**: Get instant results with visual feedback
- **Data Export**: Export all dataframes as CSV files and compress into ZIP/RAR archives
- **Responsive Design**: Support for desktop and mobile devices

## Technical Stack
- **Backend**: Flask (Python)
- **Frontend**: Bootstrap 5, Font Awesome icons, Chart.js
- **Data Storage**: JSON format for performance and maintainability
- **Export**: ZIP/RAR format support

## Key Files
- `app.py` - Flask application main file
- `basicCal.py` - Core calculation functions
- `templates/index.html` - Main page template
- `requirements.txt` - Python dependencies

## Data Files
- `expire_date.json` - Option expiration date data
- `trade_para.json` - Trading parameter data
- `tradingDay.json` - Trading day data
- `portfolio_parameters.json` - Saved parameter sets

## Recent Enhancement
Added clickable header functionality to display graphs when clicking on:
- Date headers (columns): Shows values across underlying prices
- Underlying price rows (indices): Shows values across dates
