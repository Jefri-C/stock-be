from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import requests

app = Flask(__name__)
CORS(app)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s

def get_fundamentals(ticker):
    session = make_session()
    stock = yf.Ticker(ticker, session=session)
    info = stock.info

    if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None):
        return {"error": f"No data found for '{ticker}'. Check the symbol."}

    summary = {}
    summary["Last Close Price"] = info.get("previousClose")
    summary["Market Cap"] = info.get("marketCap")
    summary["Current Price"] = info.get("currentPrice")
    summary["Shares Outstanding"] = info.get("sharesOutstanding")
    summary["52 Week High"] = info.get("fiftyTwoWeekHigh")
    summary["52 Week Low"] = info.get("fiftyTwoWeekLow")
    summary["Enterprise Value"] = info.get("enterpriseValue")
    summary["Avg Daily Volume"] = info.get("averageVolume")
    summary["P/E Ratio (TTM)"] = info.get("trailingPE")
    summary["EPS (TTM)"] = info.get("trailingEps")
    summary["Dividend Yield"] = info.get("dividendYield")
    summary["Dividend/Share"] = info.get("dividendRate")
    summary["Beta (5Y)"] = info.get("beta")
    summary["ROE"] = info.get("returnOnEquity")
    summary["Gross Margin"] = info.get("grossMargins")
    summary["Net Profit Margin"] = info.get("profitMargins")

    ebitda = info.get("ebitda")
    summary["EBITDA (TTM)"] = ebitda

    income = stock.financials
    operating_income = None
    if not income.empty:
        fy = income.columns[:2] if len(income.columns) >= 2 else income.columns
        if "Total Revenue" in income.index:
            summary["FY Revenue Current"] = income.loc["Total Revenue", fy[0]]
            if len(fy) > 1:
                summary["FY Revenue Previous"] = income.loc["Total Revenue", fy[1]]
        if "Net Income" in income.index:
            summary["FY Net Income Current"] = income.loc["Net Income", fy[0]]
            if len(fy) > 1:
                summary["FY Net Income Previous"] = income.loc["Net Income", fy[1]]
        if "Operating Income" in income.index:
            operating_income = income.loc["Operating Income", fy[0]]

    revenue = summary.get("FY Revenue Current")
    if ebitda and revenue:
        summary["EBITDA Margin"] = ebitda / revenue
    ev = summary.get("Enterprise Value")
    if ev and ebitda:
        summary["EV/EBITDA"] = ev / ebitda

    balance = stock.balance_sheet
    if not balance.empty:
        latest = balance.columns[0]
        total_assets = balance.loc["Total Assets", latest] if "Total Assets" in balance.index else None
        total_liab = balance.loc["Total Liabilities Net Minority Interest", latest] if "Total Liabilities Net Minority Interest" in balance.index else None
        cash = balance.loc["Cash And Cash Equivalents", latest] if "Cash And Cash Equivalents" in balance.index else None
        debt = balance.loc["Total Debt", latest] if "Total Debt" in balance.index else None
        equity = balance.loc["Stockholders Equity", latest] if "Stockholders Equity" in balance.index else None
        summary["Total Assets"] = total_assets
        summary["Total Liabilities"] = total_liab
        if cash is not None and debt is not None:
            summary["Net Cash Position"] = cash - debt
        shares = summary.get("Shares Outstanding")
        if equity is not None and shares:
            summary["Book Value/Share"] = equity / shares
        if debt is not None and equity is not None and equity != 0:
            summary["D/E Ratio"] = debt / equity
        if operating_income is not None and total_assets:
            summary["ROI (TTM)"] = operating_income / total_assets

    shares = summary.get("Shares Outstanding")
    net_income = summary.get("FY Net Income Current")
    if shares and net_income:
        summary["FY EPS"] = net_income / shares

    dividend = summary.get("Dividend/Share")
    eps = summary.get("EPS (TTM)")
    if dividend and eps:
        summary["Payout Ratio"] = dividend / eps

    q_income = stock.quarterly_financials
    if not q_income.empty and "Net Income" in q_income.index:
        summary["Net Income YTD"] = float(q_income.loc["Net Income"].sum())

    clean = {}
    for k, v in summary.items():
        try:
            if v is None:
                clean[k] = None
            elif hasattr(v, 'item'):
                clean[k] = v.item()
            elif hasattr(v, '__float__'):
                clean[k] = float(v)
            else:
                clean[k] = v
        except Exception:
            clean[k] = None
    return clean

@app.route("/fundamentals")
def fundamentals():
    tickers_param = request.args.get("tickers", "")
    if not tickers_param:
        return jsonify({"error": "Provide ?tickers=AAPL or ?tickers=AAPL,MSFT"}), 400
    tickers = [t.strip().upper() for t in tickers_param.split(",") if t.strip()]
    results = {}
    for ticker in tickers:
        try:
            results[ticker] = get_fundamentals(ticker)
        except Exception as e:
            results[ticker] = {"error": str(e)}
    return jsonify(results)

@app.route("/")
def health():
    return jsonify({"status": "ok", "usage": "/fundamentals?tickers=AAPL"})

app.run(host="0.0.0.0", port=8080)
