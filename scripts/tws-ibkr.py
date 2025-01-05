import threading
import time
import pandas as pd
import numpy as np
from copy import deepcopy
import sqlite3
from dotenv import load_dotenv
import os
from datetime import datetime
from decimal import Decimal
from ibapi.client import EClient
from ibapi.common import OrderId, TickAttrib, TickAttribLast
from ibapi.order_state import OrderState
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.execution import *
from ibapi.scanner import ScannerSubscription, ScanData
from pprint import pprint as pp

# Load environment variables from .env file
load_dotenv()

# Define the IBKR account number from the environment variable
IBKR_ACCOUNT_NUMBER = os.getenv("IBKR_NATIONAL_ID")


# Create the trading app
class TradingApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.hist_data = {}
        self.order_status = {}
        self.open_orders = pd.DataFrame(
            columns=[
                "permId",
                "clientId",
                "orderId",
                "account",
                "symbol",
                "secType",
                "exchange",
                "action",
                "orderType",
                "totalQuantity",
                "lmtPrice",
                "auxPrice",
                "status",
            ],
        )
        self.execution_details = pd.DataFrame(
            columns=[
                "reqId",
                "permId",
                "symbol",
                "secType",
                "currency",
                "execId",
                "time",
                "account",
                "exchange",
                "side",
                "shares",
                "price",
                "avPrice",
                "cumQty",
                "orderRef",
            ]
        )
        self.pnl_summary = pd.DataFrame(
            columns=["reqId", "dailyPnL", "unrealizedPnL", "realizedPnL"]
        )
        self.positions = pd.DataFrame(
            columns=[
                "account",
                "symbol",
                "secType",
                "currency",
                "position",
                "avgCost",
            ],
        )

        # Events
        self.contract_details_event = threading.Event()
        self.historical_data_event = threading.Event()
        self.open_order_event = threading.Event()
        self.positions_event = threading.Event()
        self.req_id_event = threading.Event()
        self.execution_event = threading.Event()

        # For ORB
        self.last_price = {}
        self.contract_id = {}
        self.pos_pnl = {}
        self.av_vol = {}
        self.hi_pri = {}
        self.lo_pri = {}

    def error(self, reqId, errorCode, errorString, advacedOrderRejectJson=""):
        print(
            "Req. ID: ",
            reqId,
            ", Error Code: ",
            errorCode,
            ", Message: ",
            errorString,
        )

    def contractDetails(self, reqId, contractDetails):
        self.contract_id[str(contractDetails.contract).split(",")[1]] = (
            contractDetails.contract.conId
        )
        print("reqId: {}, contractDetails: {}".format(reqId, contractDetails))

    def contractDetailsEnd(self, reqId):
        print("Contract Details received for reqId: {}".format(reqId))
        self.contract_details_event.set()

    def historicalData(self, reqId, bar):
        data = {
            "date ": bar.date,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": int(bar.volume),
        }

        if reqId not in self.hist_data:
            self.hist_data[reqId] = [data]
        else:
            self.hist_data[reqId].append(data)

    def historicalDataEnd(self, reqId, start, end):
        # Signal that we have received historical data
        print(
            "Req. ID: ",
            reqId,
            ", Message: Finished fetching historical data for ticker : {}".format(
                tickers[reqId]
            ),
        )
        self.historical_data_event.set()

    def reqScannerParameters(self):
        open("scanners.txt", "w").close()
        print("Scanner parameters received")

    def scannerData(
        self, reqId, rank, contractDetails, distance, benchmark, projection, legsStr
    ):
        print(
            "ScannerData. ReqId:",
            reqId,
            "Rank:",
            rank,
            "Symbol:",
            contractDetails.summary.symbol,
        )
        print(ScanData(contractDetails, rank, distance, benchmark, projection, legsStr))

    def nextValidId(self, orderId: int):
        self.nextValidOrderId = orderId
        print("NextValidId:", orderId)
        self.req_id_event.set()

    def openOrder(self, orderId, contract, order, orderState):
        self.open_orders.loc[len(self.open_orders)] = [
            order.permId,
            order.clientId,
            orderId,
            order.account,
            contract.symbol,
            contract.secType,
            contract.exchange,
            order.action,
            order.orderType,
            order.totalQuantity,
            order.lmtPrice,
            order.auxPrice,
            orderState.status,
        ]

    def openOrderEnd(self):
        self.open_order_event.set()

    def orderStatus(
        self,
        orderId: OrderId,
        status: str,
        filled: Decimal,
        remaining: Decimal,
        avgFillPrice: float,
        permId: int,
        parentId: int,
        lastFillPrice: float,
        clientId: int,
        whyHeld: str,
        mktCapPrice: float,
    ):
        super().orderStatus(
            orderId,
            status,
            filled,
            remaining,
            avgFillPrice,
            permId,
            parentId,
            lastFillPrice,
            clientId,
            whyHeld,
            mktCapPrice,
        )
        self.order_status[orderId] = {
            "status": status,
            "filled": filled,
            "remaining": remaining,
            "avgFillPrice": avgFillPrice,
            "permId": permId,
            "parentId": parentId,
            "lastFillPrice": lastFillPrice,
            "clientId": clientId,
            "whyHeld": whyHeld,
            "mktCapPrice": mktCapPrice,
        }

    def execDetails(self, reqId, contract, execution):
        self.execution_details.loc[len(self.execution_details)] = [
            reqId,
            execution.permId,
            contract.symbol,
            contract.secType,
            contract.currency,
            execution.execId,
            execution.time,
            execution.acctNumber,
            execution.exchange,
            execution.side,
            execution.shares,
            execution.price,
            execution.avgPrice,
            execution.cumQty,
            execution.orderRef,
        ]

    def execDetailsEnd(self, reqId: int):
        self.execution_event.set()

    def position(
        self, account: str, contract: Contract, position: Decimal, avgCost: float
    ):
        data = {
            "account": account,
            "symbol": contract.symbol,
            "secType": contract.secType,
            "currency": contract.currency,
            "position": position,
            "avgCost": avgCost,
        }
        data = pd.DataFrame([data])
        if self.positions.empty:
            self.positions = data
        elif self.positions["symbol"].str.contains(contract.symbol).any():
            self.positions.loc[
                self.positions["symbol"] == contract.symbol, "position"
            ] = position
            self.positions.loc[
                self.positions["symbol"] == contract.symbol, "AvgCost"
            ] = avgCost
        else:
            self.positions = pd.concat([self.positions, data], ignore_index=True)

    def positionEnd(self):
        self.positions_event.set()

    def pnl(self, reqId, dailyPnL, unrealizedPnL, realizedPnL):
        data = {
            "reqId": reqId,
            "dailyPnL": dailyPnL,
            "unrealizedPnL": unrealizedPnL,
            "realizedPnL": realizedPnL,
        }
        self.pnl_summary.append(data, ignore_index=True)

    def pnlSingle(self, reqId, pos, dailyPnL, unrealizedPnL, realizedPnL, value):
        print("PnL Single. ReqId:", reqId, "Pos:", pos, "Daily PnL:", dailyPnL)

    def tickByTickAllLast(
        self,
        reqId: int,
        tickType: int,
        time: int,
        price: float,
        size: Decimal,
        tickAtrribLast: TickAttribLast,
        exchange: str,
        specialConditions: str,
    ):
        if tickType == 1:
            print("Last.", end="")
        else:
            db = sqlite3.connect("tws-ibkr.db")
            c = db.cursor()
            print("AllLast.", end="")
            print(
                "ReqId:",
                reqId,
                "Time:",
                datetime.fromtimestamp(time).strftime("%Y%m%d %H:%M:%S"),
                "Price:",
                price,
                "Size:",
                size,
                "Exch:",
                exchange,
                "Spec Cond:",
                specialConditions,
                "PastLimit:",
                tickAtrribLast.pastLimit,
                "Unreported:",
                tickAtrribLast.unreported,
            )
            values = (
                datetime.fromtimestamp(time).strftime("%Y%m%d %H:%M:%S.%f"),
                price,
                size,
            )
            try:
                query = "INSERT INTO {} (Time, Price, Volume) VALUES (?, ?, ?)".format(
                    tickers[reqId]
                )
                c.execute(query, values)
                db.commit()
            except Exception as e:
                print("Error inserting tick data:", e)
                db.rollback()

    def tickString(self, reqId, tickType, value: str):
        print("TickString. TickerId:", reqId, "Type:", tickType, "Value:", value)
        values = value.split(";")
        if tickType == 48:
            print(
                "TickString. TickerId:",
                reqId,
                "Type:",
                tickType,
                "Last Price:",
                values[0],
                "Last Size:",
                values[1],
                "Last Time:",
                values[2],
                "Volume:",
                values[3],
                "VWAP:",
                values[4],
                "Single Trade:",
                values[5],
            )

    def tickPrice(self, reqId, tickType, price, attrib):
        if tickType == 4:
            self.last_price[reqId] = price


def websocket_con():
    app.run()
    if event.is_set():
        app.close()


# Connect to TWS
app = TradingApp()
app.connect("127.0.0.1", 7497, clientId=0)

event = threading.Event()
conn_thread = threading.Thread(target=websocket_con)
conn_thread.start()
time.sleep(1)


# Database functions


def createDBTables(tickers):
    db = sqlite3.connect("tws-ibkr.db")
    c = db.cursor()
    for ticker in tickers:
        c.execute(
            """CREATE TABLE IF NOT EXISTS {} (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Time DATETIME,
            Price REAL,
            Volume INTEGER,
        )""".format(
                ticker
            )
        )
    c.close()


def inspectDBTables(tickers):
    db = sqlite3.connect("tws-ibkr.db")
    c = db.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print(c.fetchall())
    c.execute("PRAGMA table_info({})".format(tickers[0]))
    print(c.fetchall())
    c.execute("PRAGMA table_info({})".format(tickers[1]))
    print(c.fetchall())
    c.execute("SELECT * FROM {}".format(tickers[0]))
    print(c.fetchall())
    c.execute("SELECT * FROM {}".format(tickers[1]))
    print(c.fetchall())
    c.close()


def getCandlesFromTicks(ticker, start, end):
    db_main = sqlite3.connect("tws-ibkr.db")
    data = pd.read_sql(
        """SELECT * FROM {} WHERE Time BETWEEN '{}' AND '{}'""".format(
            ticker, start, end
        ),
        con=db_main,
    )
    data = data.set_index("Time")
    data.index = pd.to_datetime(data.index)
    ohlc = data.loc[:, ["Price"]].resample("5 min").ohlc().dropna()
    ohlc.columns = ["Open", "High", "Low", "Close"]
    vol = data.loc[:, ["Volume"]].resample("5 min").sum()
    ohlc["Volume"] = vol
    ohlcv = ohlc.merge(vol, left_index=True, right_index=True)
    return ohlc


# Data functions


def getContract(symbol, secType="STK", currency="USD", exchange="NASDAQ"):
    contract = Contract()
    contract.symbol = symbol
    contract.secType = secType
    contract.currency = currency
    contract.exchange = exchange
    return contract


def getHistoricalData(
    tickers,
    secType="STK",
    currency="USD",
    exchange="NASDAQ",
    durationStr="1 M",
    barSizeSetting="5 mins",
    whatToShow="ADJUSTED_LAST",
):
    app.hist_data = {}
    for i, ticker in enumerate(tickers):
        app.historical_data_event.clear()
        app.reqHistoricalData(
            reqId=i,
            contract=getContract(ticker, secType, currency, exchange),
            endDateTime="",
            durationStr=durationStr,
            barSizeSetting=barSizeSetting,
            whatToShow=whatToShow,
            useRTH=1,
            formatDate=1,
            keepUpToDate=False,
            chartOptions=[],
        )
        app.historical_data_event.wait()
    df_dict = {}
    for ticker in tickers:
        df_dict[ticker] = pd.DataFrame(app.hist_data[tickers.index(ticker)])
        df_dict[ticker].set_index("date ", inplace=True)
    return df_dict


def getcontractDetails(app, contract):
    app.contract_details_event.clear()
    app.reqContractDetails(1, contract)
    app.contract_details_event.wait()


def streamData(req_num, tickers):
    """stream tick level data"""
    for ticker in tickers:
        app.reqTickByTickData(
            reqId=req_num,
            contract=getContract(ticker),
            tickType="AllLast",
            numberOfTicks=0,
            ignoreSize=True,
        )


def streamSnapshotData(req_num, tickers):
    for ticker in tickers:
        app.reqMktData(
            reqId=req_num,
            contract=getContract(ticker),
            genericTickList="",
            snapshot=False,
            regulatorySnapshot=False,
        )


# Market Scanners


def scannerParameters():
    app.reqScannerParameters()


def scannerSubscription():
    scan_obj = ScannerSubscription()
    scan_obj.numberOfRows = 10
    scan_obj.instrument = "STK"
    scan_obj.locationCode = "STK.NSE"
    scan_obj.scanCode = "HIGH_OPEN_GAP"
    app.reqScannerSubscription(1, scan_obj)
    time.sleep(30)
    app.cancelScannerSubscription(1)


# Order functions


def getNextValidOrderId():
    app.req_id_event.clear()
    app.reqIds(-1)
    app.req_id_event.wait()
    return app.nextValidOrderId


def mktOrder(action, quantity):
    order = Order()
    order.action = action
    order.totalQuantity = quantity
    order.orderType = "MKT"
    return order


def lmtOrder(action, quantity, lmtPrice=0):
    order = Order()
    order.action = action
    order.totalQuantity = quantity
    order.lmtPrice = lmtPrice
    order.orderType = "LMT"
    return order


def stpOrder(direction, quantity, stopPrice):
    order = Order()
    order.action = direction
    order.orderType = "STP"
    order.totalQuantity = quantity
    order.auxPrice = stopPrice
    return order


def trailStpOrder(direction, quantity, trailPercent, trailPrice, stopPrice):
    order = Order()
    order.action = direction
    order.orderType = "TRAIL"
    order.totalQuantity = quantity
    order.trailingPercent = trailPercent
    # order.auxPrice = trailPrice
    order.trailStopPrice = stopPrice  # Not necessary to give this

    return order


def bktOrder(order_id, direction, quantity, lmtPrice, stopPrice, profitPrice):
    parent = Order()
    parent.orderId = order_id
    parent.action = direction
    parent.orderType = "LMT"
    parent.totalQuantity = quantity
    parent.lmtPrice = lmtPrice
    parent.transmit = False

    stop = Order()
    stop.orderId = order_id + 1
    stop.action = "SELL" if direction == "BUY" else "BUY"
    stop.orderType = "STP"
    stop.totalQuantity = quantity
    stop.auxPrice = stopPrice
    stop.parentId = order_id
    stop.transmit = False

    profit = Order()
    profit.orderId = order_id + 2
    profit.action = "SELL" if direction == "BUY" else "BUY"
    profit.orderType = "LMT"
    profit.totalQuantity = quantity
    profit.lmtPrice = profitPrice
    profit.parentId = order_id
    profit.transmit = True

    bracketOrder = [parent, stop, profit]
    return bracketOrder


# Account level data functions


def getOpenOrders():
    app.open_orders = pd.DataFrame(columns=app.open_orders.columns)
    app.open_order_event.clear()
    app.reqOpenOrders()
    app.open_order_event.wait()
    return app.open_orders


def getPositions():
    app.positions = pd.DataFrame(columns=app.positions.columns)
    app.positions_event.clear()
    app.reqPositions()
    app.positions_event.wait()
    return app.positions


def getInitialPositions(tickers):
    initial_positions = {key: 0 for key in tickers}
    initial_positions_df = app.positions[app.positions["symbol"].isin(tickers)]
    for key in initial_positions_df["symbol"]:
        initial_positions[key] = int(
            initial_positions_df[initial_positions_df["symbol"] == key][
                "position"
            ].values[0]
        )
    return initial_positions


def getExecutions():
    app.execution_details = pd.DataFrame(columns=app.execution_details.columns)
    app.execution_event.clear()
    app.reqExecutions(-1, ExecutionFilter())
    app.execution_event.wait()
    return app.execution_details


def getPnL(reqId):
    app.pnl_summary = pd.DataFrame(columns=app.pnl_summary.columns)
    app.reqPnL(reqId, IBKR_ACCOUNT_NUMBER, "")
    time.sleep(1)
    app.cancelPnL(reqId)


def getPnLSingle(reqId):
    app.reqPnLSingle(reqId, IBKR_ACCOUNT_NUMBER, "", app.contract_id)


# Indicator functions


# Lagging momentum indicator (Gives many false signals in sideways market)
def MACD(DF, a=12, b=26, c=9):
    df = DF.copy()
    df["MA_Fast"] = df["close"].ewm(span=a, min_periods=a).mean()
    df["MA_Slow"] = df["close"].ewm(span=b, min_periods=b).mean()
    df["MACD"] = df["MA_Fast"] - df["MA_Slow"]
    df["signal"] = df["MACD"].ewm(span=c, min_periods=c).mean()
    return df


# Overbought/Oversold indicators (emerging markets: 80/20, developed markets: 70/30)
def RSI(DF, n=14):
    df = DF.copy()
    df["delta"] = df["close"] - df["close"].shift(1)
    df["gain"] = np.where(df["delta"] >= 0, df["delta"], 0)
    df["loss"] = np.where(df["delta"] < 0, abs(df["delta"]), 0)
    avg_gain = []
    avg_loss = []
    gain = df["gain"].tolist()
    loss = df["loss"].tolist()
    for i in range(len(df)):
        if i < n:
            avg_gain.append(np.NaN)
            avg_loss.append(np.NaN)
        elif i == n:
            avg_gain.append(df["gain"].rolling(n).mean().tolist()[n])
            avg_loss.append(df["loss"].rolling(n).mean().tolist()[n])
        elif i > n:
            avg_gain.append(
                (avg_gain[i - 1] * (n - 1) + gain[i]) / n
            )  # (prev_avg_gain*(n-1) + current_gain)/n
            avg_loss.append(
                (avg_loss[i - 1] * (n - 1) + loss[i]) / n
            )  # (prev_avg_loss*(n-1) + current_loss)/n
    df["avg_gain"] = np.array(avg_gain)
    df["avg_loss"] = np.array(avg_loss)
    df["rs"] = df["avg_gain"] / df["avg_loss"]
    df["rsi"] = 100 - (100 / (1 + df["rs"]))
    return df


# Volatility indicator
def BollingerBands(DF, n=20):
    df = DF.copy()
    df["MA"] = df["close"].ewm(span=n, min_period=n).mean()
    df["BB_up"] = df["MA"] + 2 * df["close"].rolling(n).std(ddof=0)
    df["BB_dn"] = df["MA"] - 2 * df["close"].rolling(n).std(ddof=0)
    df["BB_width"] = df["BB_up"] - df["BB_dn"]
    return df


# Volatility indicator
def ATR(DF, n=20):
    df = DF.copy()
    df["H-L"] = abs(df["high"] - df["low"])
    df["H-PC"] = abs(df["high"] - df["close"].shift(1))
    df["L-PC"] = abs(df["low"] - df["close"].shift(1))
    df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1, skipna=False)
    # df["ATR"] = df["TR"].rolling(n).mean()
    # df["ATR"] = df["TR"].ewm(span=n, min_periods=n).mean()
    df["ATR"] = df["TR"].ewm(com=n, min_periods=n).mean()
    return df


# Trend Strength Indicator (0-25: Absent, 25-50: Weak, 50-75: Strong, 75-100: Very Strong)
def ADX(DF, n=14):
    df2 = DF.copy()
    df2["H-L"] = df2["high"] - df2["low"]
    df2["H-PC"] = abs(df2["high"] - df2["close"].shift(1))
    df2["L-PC"] = abs(df2["low"] - df2["close"].shift(1))
    df2["TR"] = df2[["H-L", "H-PC", "L-PC"]].max(axis=1, skipna=False)
    df2["DMplus"] = np.where(
        (df2["high"] - df2["high"].shift(1)) > (df2["low"].shift(1) - df2["low"]),
        df2["high"] - df2["high"].shift(1),
        0,
    )
    df2["DMplus"] = np.where(df2["DMplus"] < 0, 0, df2["DMplus"])
    df2["DMminus"] = np.where(
        (df2["low"].shift(1) - df2["low"]) > (df2["high"] - df2["high"].shift(1)),
        df2["low"].shift(1) - df2["low"],
        0,
    )
    df2["DMminus"] = np.where(df2["DMminus"] < 0, 0, df2["DMminus"])
    TRn = []
    DMplusN = []
    DMminusN = []
    TR = df2["TR"].tolist()
    DMplus = df2["DMplus"].tolist()
    DMminus = df2["DMminus"].tolist()
    for i in range(len(df2)):
        if i < n:
            TRn.append(np.NaN)
            DMplusN.append(np.NaN)
            DMminusN.append(np.NaN)
        elif i == n:
            TRn.append(df2["TR"].rolling(n).sum().tolist()[n])
            DMplusN.append(df2["DMplus"].rolling(n).sum().tolist()[n])
            DMminusN.append(df2["DMminus"].rolling(n).sum().tolist()[n])
        elif i > n:
            TRn.append(TRn[i - 1] - (TRn[i - 1] / n) + TR[i])
            DMplusN.append(DMplusN[i - 1] - (DMplusN[i - 1] / n) + DMplus[i])
            DMminusN.append(DMminusN[i - 1] - (DMminusN[i - 1] / n) + DMminus[i])
    df2["TRn"] = np.array(TRn)
    df2["DMplusN"] = np.array(DMplusN)
    df2["DMminusN"] = np.array(DMminusN)
    df2["DIplusN"] = (DMplusN / TRn) * 100
    df2["DIminusN"] = (DMminusN / TRn) * 100
    df2["DIdiff"] = abs(df2["DIplusN"] - df2["DIminusN"])
    df2["DIsum"] = df2["DIplusN"] + df2["DIminusN"]
    df2["DX"] = (df2["DIdiff"] / df2["DIsum"]) * 100  # Directional Index
    ADX = []
    DX = df2["DX"].tolist()
    for j in range(len(df2)):
        if j < 2 * n - 1:
            ADX.append(np.NaN)
        elif j == 2 * n - 1:
            ADX.append(df2["DX"][j - n + 1 : j + 1].mean())
        elif j > 2 * n - 1:
            ADX.append(((n - 1) * ADX[j - 1] + DX[j]) / n)  # ADX = ((n-1)*ADX + DX)/n
    df2["ADX"] = np.array(ADX)
    return df2


# Overbought/Oversold indicator (80/20 for emerging markets, 70/30 for developed markets)
def Stochastic(DF, n=20, a=3):
    df = DF.copy()
    df["C-L"] = df["close"] - df["low"].rolling(n).min()
    df["H-L"] = df["high"].rolling(n).max() - df["low"].rolling(n).min()
    df["%K"] = df["C-L"] / df["H-L"] * 100
    # df["%D"] = df["%K"].ewm(span=a, min_periods=a).mean()
    df["%D"] = df["%K"].rolling(a).mean()
    return df


# KPI functions


def CAGR(DF, candles_per_day=1):
    df = DF.copy()
    df["cum_return"] = (1 + df["ret"]).cumprod()
    n = len(df) / (252 * candles_per_day)
    CAGR = (df["cum_return"].tolist()[-1]) ** (1 / n) - 1
    return CAGR


def volatility(DF, candles_per_day=1):
    df = DF.copy()
    vol = df["ret"].std() * np.sqrt(252 * candles_per_day)
    return vol


def sharpe(DF, rf=0.03, candles_per_day=1):
    df = DF.copy()
    sr = (CAGR(df, candles_per_day) - rf) / volatility(df, candles_per_day)
    return sr


def max_dd(DF):
    df = DF.copy()
    df["cum_return"] = (1 + df["ret"]).cumprod()
    df["cum_roll_max"] = df["cum_return"].cummax()
    df["drawdown"] = df["cum_roll_max"] - df["cum_return"]
    df["drawdown_pct"] = df["drawdown"] / df["cum_roll_max"]
    max_dd = df["drawdown_pct"].max()
    return max_dd


# Intraday KPI functions


def winRate(DF):
    "function to calculate win rate of intraday trading strategy"
    df = DF["ret"]
    pos = df[df > 1]
    neg = df[df < 1]
    return (len(pos) / len(pos + neg)) * 100


def meanretpertrade(DF):
    df = DF["ret"]
    df_temp = (df - 1).dropna()
    return df_temp[df_temp != 0].mean()


def meanretwintrade(DF):
    df = DF["ret"]
    df_temp = (df - 1).dropna()
    return df_temp[df_temp > 0].mean()


def meanretlostrade(DF):
    df = DF["ret"]
    df_temp = (df - 1).dropna()
    return df_temp[df_temp < 0].mean()


def maxconsectvloss(DF):
    df = DF["ret"]
    df_temp = df.dropna(axis=0)
    df_temp2 = np.where(df_temp < 1, 1, 0)
    count_consecutive = []
    seek = 0
    for i in range(len(df_temp2)):
        if df_temp2[i] == 0:
            seek = 0
        else:
            seek = seek + 1
            count_consecutive.append(seek)
    return max(count_consecutive)


most_traded_25_nasdaq = [
    "META",
    "AMZN",
    "INTC",
    "MSFT",
    "AAPL",
    "GOOGL",
    "CSCO",
    "CMCSA",
    "ADBE",
    "NVDA",
    "NFLX",
    "PYPL",
    "AMGN",
    "AVGO",
    "TXN",
    "CHTR",
    "QCOM",
    "GILD",
    "FISV",
    "BKNG",
    "INTU",
    "ADP",
    "CME",
    "TMUS",
    "MU",
]

# BackTest Strategies


class TradingStrategy:
    def __init__(
        self,
        tickers,
        secType,
        currency,
        exchange,
        capital_per_trade,
        durationStr="1 M",
        interval_in_mins=15,
    ):
        self.tickers = tickers
        self.secType = secType
        self.currency = currency
        self.exchange = exchange
        self.durationStr = durationStr
        self.interval_in_mins = interval_in_mins
        self.barSizeSetting = self.get_bar_size_string(interval_in_mins)
        self.trade_pos = {}
        self.trade_sig = {}
        self.trade_cou = {}
        self.trade_dat = {}
        self.trade_ret = {}
        self.capital_per_trade = capital_per_trade
        self.ohlcv = deepcopy(
            getHistoricalData(
                tickers,
                secType=secType,
                currency=currency,
                exchange=exchange,
                durationStr=durationStr,
                barSizeSetting=self.barSizeSetting,
            )
        )
        for ticker in tickers:
            self.trade_pos[ticker] = "Closed"
            self.trade_sig[ticker] = [None]
            self.trade_cou[ticker] = 0
            self.trade_dat[ticker] = {}
            self.trade_ret[ticker] = [0]

    def get_bar_size_string(self, bar_size_in_mins):
        # Define valid bar sizes as a dictionary for clarity
        valid_bar_sizes = {
            "secs": [1, 5, 10, 15, 30],
            "mins": [1, 2, 3, 5, 10, 15, 20, 30],
            "hrs": [1, 2, 3, 4, 8],
            "days": [1],
            "weeks": [1],
            "months": [1],
        }

        # Check if the input corresponds to "mins"
        if bar_size_in_mins in valid_bar_sizes["mins"]:
            return f"{int(bar_size_in_mins)} mins"
        # Check if the input corresponds to "secs"
        elif (
            bar_size_in_mins < 1 and (bar_size_in_mins * 60) in valid_bar_sizes["secs"]
        ):
            return f"{int(bar_size_in_mins * 60)} secs"
        # Check if the input corresponds to "hrs"
        elif (
            bar_size_in_mins % 60 == 0
            and (bar_size_in_mins // 60) in valid_bar_sizes["hrs"]
        ):
            return f"{int(bar_size_in_mins // 60)} hrs"
        # Check if the input corresponds to "days"
        elif (
            bar_size_in_mins == 1440 and 1 in valid_bar_sizes["days"]
        ):  # 1440 mins = 1 day
            return "1 day"
        # Check if the input corresponds to "weeks"
        elif (
            bar_size_in_mins == 10080 and 1 in valid_bar_sizes["weeks"]
        ):  # 10080 mins = 1 week
            return "1 week"
        # Check if the input corresponds to "months"
        elif (
            bar_size_in_mins == 43200 and 1 in valid_bar_sizes["months"]
        ):  # 43200 mins = 1 month
            return "1 month"
        else:
            # Raise an exception if the bar size is not supported
            raise ValueError(f"Bar size {bar_size_in_mins} mins is not supported")


class MACD_Stochastic_ATR_Strategy(TradingStrategy):
    def __init__(
        self,
        tickers,
        secType,
        currency,
        exchange,
        capital_per_trade=1000,
        interval_in_mins=15,
        backtest=True,
    ):
        durationStr = "1 Y" if backtest else "1 M"
        super().__init__(
            tickers,
            secType,
            currency,
            exchange,
            capital_per_trade,
            durationStr,
            interval_in_mins,
        )
        self.tickers = tickers
        self.ohlcv_snapshots = {}
        self.iter = 0
        self._refresh_data(history=False)

    def run(self, duration=1):
        if self.backtest == True:
            self.backtest()
        else:
            self.live_trade(duration)

    def live_trade(self, duration):
        starttime = time.time()
        timeout = starttime + 60 * 60 * duration
        while time.time() < timeout:
            print(
                f"Live trading session started, this is iteration {self.iter} and the time is {datetime.now()}"
            )
            self._refresh_data(
                durationStr=self.durationStr,
                barSizeSetting=self.barSizeSetting,
                history=True,
            )
            for ticker in self.tickers:
                quantity = int(
                    self.capital_per_trade / self.ohlcv[ticker]["close"].iloc[-1]
                )
                positions = getPositions()
                orders = getOpenOrders()
                contract = getContract(
                    ticker, self.secType, self.currency, self.exchange
                )

                if quantity == 0:
                    self.trade_ret[ticker].append(0)
                    continue
                if len(positions) == 0:
                    self.execute_live_trade(ticker, contract, quantity)
                elif ticker not in positions["symbol"].tolist():
                    self.execute_live_trade(ticker, contract, quantity)
                else:
                    initial_positions = getInitialPositions(self.tickers)
                    if (
                        positions[positions["symbol"] == ticker]["position"].values[-1]
                        == initial_positions[ticker]
                    ):
                        self.execute_live_trade(ticker, contract, quantity)
                    else:
                        self.replace_stop_order(ticker, orders)

                # Check executions and update the necessary trade data

            time.sleep(
                (self.interval_in_mins * 60)
                - ((time.time() - starttime) % (self.interval_in_mins * 60))
            )

    def _refresh_data(
        self,
        durationStr="1 M",
        barSizeSetting="15 mins",
        history=True,
    ):
        if history:
            self.ohlcv = deepcopy(
                getHistoricalData(
                    tickers,
                    self.secType,
                    self.currency,
                    self.exchange,
                    durationStr,
                    barSizeSetting,
                )
            )
        for ticker in self.tickers:
            self.ohlcv[ticker]["stoch"] = Stochastic(self.ohlcv[ticker])["%D"]
            macd = MACD(self.ohlcv[ticker])
            self.ohlcv[ticker]["macd"] = macd["MACD"]
            self.ohlcv[ticker]["signal"] = macd["signal"]
            self.ohlcv[ticker]["atr"] = ATR(self.ohlcv[ticker], 60)["ATR"]
            self.ohlcv[ticker].dropna(inplace=True)
        if history:
            for ticker in self.tickers:
                if self.ohlcv[ticker].index[-1] not in self.data[ticker].index:
                    self.data[ticker] = pd.concat(
                        [self.data[ticker], self.ohlcv[ticker].iloc[-1].to_frame().T]
                    )
        else:
            self.data = deepcopy(self.ohlcv)
        self.ohlcv_snapshots[self.iter] = deepcopy(self.ohlcv)
        self.iter += 1

    def execute_live_trade(self, ticker, contract, quantity):
        if self.buy_condition(ticker, -1):
            self.trade_sig[ticker].append("Buy")
            ordId = getNextValidOrderId()
            mkt_order = mktOrder("BUY", quantity)
            app.placeOrder(
                ordId,
                contract,
                mkt_order,
            )
            print(
                "Order placement requested for {} at time {}".format(
                    ticker, datetime.now()
                )
            )
            app.open_order_event.wait()
            getOpenOrders()
            app.open_order_event.clear()
            print("Open Orders: \n", app.open_orders)
            print("Order Status Keys: \n", app.order_status.keys)
            print("Execution Details: \n", app.execution_details)
            print("Execution Details: \n", app.positions)

            print("Order status: ", app.order_status[ordId]["status"])
            while app.order_status[ordId]["status"] not in [
                "Filled",
                "Cancelled",
                "Inactive",
            ]:
                print("Order status: ", app.order_status[ordId]["status"])
                time.sleep(1)
            print("Order status: ", app.order_status[ordId]["status"])
            if app.order_status[ordId]["status"] == "Filled":
                self.trade_cou[ticker] += 1
                self.trade_dat[ticker][self.trade_cou[ticker]] = [
                    app.order_status[ordId]["avgFillPrice"]
                ]
                # stp_qty = (
                #     app.positions[app.positions["Symbol"] == ticker]["Position"]
                #     .sort_values(ascending=True)
                #     .values[-1]
                # )
                stp_qty = app.order_status[ordId]["filled"]
                stp_order = stpOrder(
                    "SELL",
                    stp_qty,
                    round(self.stop_price(ticker, 0), 2),
                )
                app.placeOrder(
                    ordId + 1,
                    getContract(ticker),
                    stp_order,
                )
                print("Open Orders: \n", app.open_orders)
                print("Order Status Keys: \n", app.order_status.keys)
                print("Execution Details: \n", app.execution_details)
                print("Execution Details: \n", app.positions)
            self.trade_ret[ticker].append(0)

    def execute_back_trade(self, ticker, i):
        if self.trade_pos[ticker] == "Closed":
            if self.buy_condition(ticker, i):
                self.trade_pos[ticker] = "Open"
                self.trade_sig[ticker].append("Buy")
                self.trade_cou[ticker] += 1
                self.trade_dat[ticker][self.trade_cou[ticker]] = [self.price(ticker, i)]
            else:
                self.trade_sig[ticker].append(None)
            # No returns while position is closed
            self.trade_ret[ticker].append(0)

        elif self.trade_pos[ticker] == "Open":
            if self.sell_condition(ticker, i):
                self.trade_pos[ticker] = "Closed"
                self.trade_sig[ticker].append("Sell")
                self.trade_dat[ticker][self.trade_cou[ticker]].append(
                    self.stop_price(ticker, i)
                )
                self.trade_cou[ticker] += 1
                self.trade_ret[ticker].append(self.ret(ticker, i, stop=True))
            else:
                self.trade_sig[ticker].append("Hold")
                self.trade_ret[ticker].append(self.ret(ticker, i, stop=False))

    def replace_stop_order(self, ticker, contract, orders):
        ord_id = (
            orders[orders["Symbol"] == ticker]["OrderID"]
            .sort_values(ascending=True)
            .values[-1]
        )
        old_qty = app.order_status[ord_id]["filled"]
        app.cancelOrder(ord_id)
        ord_id = getNextValidOrderId()
        stp_order = stpOrder(
            ord_id,
            old_qty,
            round(self.stop_price(ticker, 0), 2),
        )
        app.placeOrder(
            ord_id,
            contract,
            stp_order,
        )

    def buy_condition(self, ticker, i):
        # return (
        #     self.ohlcv[ticker]["macd"].iloc[i] > self.ohlcv[ticker]["signal"].iloc[i]
        #     and self.ohlcv[ticker]["stoch"].iloc[i] > 30
        #     and self.ohlcv[ticker]["stoch"].iloc[i]
        #     > self.ohlcv[ticker]["stoch"].iloc[i - 1]
        # )
        return True

    def sell_condition(self, ticker, i):
        return (
            self.ohlcv[ticker]["low"].iloc[i]
            < self.ohlcv[ticker]["close"].iloc[i - 1]
            - self.ohlcv[ticker]["atr"].iloc[i - 1]
        )

    def price(self, ticker, i):
        return self.ohlcv[ticker]["close"].iloc[i]

    def stop_price(self, ticker, i):
        return self.price(ticker, i - 1) - self.ohlcv[ticker]["atr"].iloc[i - 1]

    def ret(self, ticker, i, stop=False):
        if stop:
            return (self.stop_price(ticker, i) / self.price(ticker, i - 1)) - 1
        else:
            return (self.price(ticker, i) / self.price(ticker, i - 1)) - 1

    def backtest(self):
        for ticker in self.tickers:
            for i in range(1, len(self.ohlcv[ticker])):
                self.execute_back_trade(ticker, i)
            if self.trade_cou[ticker] % 2 != 0:
                self.trade_dat[ticker][self.trade_cou[ticker]].append(
                    self.ohlcv[ticker]["close"].iloc[i]
                )
        for ticker in self.tickers:
            self.ohlcv[ticker]["ret"] = np.array(self.trade_ret[ticker])
            self.ohlcv[ticker]["pos"] = np.array(self.trade_sig[ticker])
            self.trade_dat[ticker] = pd.DataFrame(self.trade_dat[ticker]).T
            self.trade_dat[ticker].columns = ["entry_price", "exit_price"]
            self.trade_dat[ticker]["ret"] = (
                self.trade_dat[ticker]["exit_price"]
                / self.trade_dat[ticker]["entry_price"]
            )
            self.ohlcv[ticker].to_csv("{}_ohlcv_class.csv".format(ticker))
        return self.ohlcv, self.trade_dat, self.trade_cou


def ORB_Prep(tickers, kill_event):
    # Get historical data for the tickers every 15 mins
    first_pass_flag = True
    while not kill_event.is_set():
        app.hist_data = {}
        start_time = time.time()
        for i, ticker in enumerate(tickers):
            app.historical_data_event.clear()
            getHistoricalData(
                i,
                getContract(ticker),
                durationStr="5 D" if first_pass_flag else "1 D",
                barSizeSetting="15 mins" if first_pass_flag else "5 min",
            )
            app.historical_data_event.wait()
            if first_pass_flag:
                tot_vol = app.hist_data[i]["Volume"].sum()
                num_vol_bars = len(app.hist_data[i])
                app.av_vol[i] = int(tot_vol / num_vol_bars * 3)
                app.hi_pri[i] = app.hist_data[i][-1]["High"]
                app.lo_pri[i] = app.hist_data[i][-1]["Low"]
        first_pass_flag = False
        time.sleep(900 - (time.time() - start_time) % 900)


def Open_Range_Breakout_Strategy(
    tickers, kill_event, profit_limit=1000, loss_limit=500, pos_size=10000
):
    """
    Check whether the kill switch activated (p&l reached daily target)
    Check whether the ticker has an open order or open position
    Check the last traded price and compare it with high and low price, if it breaches either, we will place the order
    If price breaches the high, we will place a buy order with stop loss at low and vice versa
    If price points breach, check the volume of the current ticker and if there is a spike in volume, we will place the order if it is twice the average volume
    If the order is placed, we will check the position and if the position is closed, we will place the stop loss order
    """
    while not kill_event.is_set():
        for ticker in tickers:
            OrderRefresh()
            current_total_pnl = sum(app.pos_pnl.values())
            [hour, minute] = time.strftime("%H:%M").split(":")

            if (
                current_total_pnl > profit_limit
                or current_total_pnl < loss_limit
                or int(hour) > 21
                or int(minute) > 30
            ):
                kill_event.set()
                print("Total PnL: ", sum(app.pos_pnl.values()))
                app.reqGlobalCancel()
                close_all_positions()
                continue

            if (
                len(app.execution_df[app.execution_df["Symbol"] == ticker]) == 0
                and len(app.openOrders_df[app.openOrders_df["Symbol"] == ticker]) == 0
            ):
                if app.av_vol[ticker] * 2 < app.hist_data[ticker][-1]["Volume"]:
                    if app.hist_data[ticker][-1]["High"] > app.hi_pri[ticker]:
                        quantity = pos_size / app.last_price[tickers.index(ticker)]
                        lmt_price = app.hist_data[ticker][-1]["High"]
                        tp_price = round(
                            app.last_price[tickers.index(ticker)] * 1.05, 2
                        )
                        sl_price = app.lo_pri[ticker]
                        app.reqIds(-1)
                        ord_id = app.nextValidOrderId
                        bkt_order = bktOrder(
                            ord_id, "BUY", quantity, lmt_price, sl_price, tp_price
                        )
                        for o in bkt_order:
                            app.placeOrder(o.orderId, getContract(ticker), o)

                    if app.hist_data[ticker][-1]["Low"] < app.lo_pri[ticker]:
                        quantity = pos_size / app.last_price[tickers.index(ticker)]
                        lmt_price = app.hist_data[ticker][-1]["Low"]
                        tp_price = round(
                            app.last_price[tickers.index(ticker)] * 0.95, 2
                        )
                        sl_price = app.hi_pri[ticker]
                        app.reqIds(-1)
                        ord_id = app.nextValidOrderId
                        bkt_order = bktOrder(
                            ord_id, "SELL", quantity, lmt_price, sl_price, tp_price
                        )
                        for o in bkt_order:
                            app.placeOrder(o.orderId, getContract(ticker), o)


# Analysis functions


def compute_KPI(df, tickers):
    cagr = []
    vltlty = []
    shrp = []
    max_ddwn = []
    for ticker in tickers:
        cagr.append(CAGR(df[ticker], candles_per_day=375.0 / 15.0))
        vltlty.append(volatility(df[ticker], candles_per_day=375.0 / 15.0))
        shrp.append(sharpe(df[ticker], candles_per_day=375.0 / 15.0))
        max_ddwn.append(max_dd(df[ticker]))
    strategy_df = pd.DataFrame()
    for ticker in tickers:
        strategy_df[ticker] = df[ticker]["ret"]
    strategy_df["ret"] = strategy_df.mean(axis=1)
    cagr.append(
        CAGR(strategy_df, candles_per_day=375.0 / 15.0)
    )  # Trading time: 375 mins for Indian markets, 390 mins for US markets
    vltlty.append(volatility(strategy_df, candles_per_day=375.0 / 15.0))
    shrp.append(sharpe(strategy_df, candles_per_day=375.0 / 15.0))
    max_ddwn.append(max_dd(strategy_df))
    KPI_df = pd.DataFrame(
        {
            "CAGR": cagr,
            "Volatility": vltlty,
            "Sharpe Ratio": shrp,
            "Max Drawdown": max_ddwn,
        },
        index=tickers + ["Strategy"],
    ).T
    return KPI_df


def compute_intraday_KPIs(df, tickers):
    win_rate = {}
    mean_ret_pt = {}
    mean_ret_pwt = {}
    mean_ret_plt = {}
    max_cons_loss = {}
    for ticker in tickers:
        print("calculating intraday KPIs for ", ticker)
        win_rate[ticker] = winRate(df[ticker])
        mean_ret_pt[ticker] = meanretpertrade(df[ticker])
        mean_ret_pwt[ticker] = meanretwintrade(df[ticker])
        mean_ret_plt[ticker] = meanretlostrade(df[ticker])
        max_cons_loss[ticker] = maxconsectvloss(df[ticker])

    KPI_df = pd.DataFrame(
        [win_rate, mean_ret_pt, mean_ret_pwt, mean_ret_plt, max_cons_loss],
        index=[
            "Win Rate",
            "Mean Return Per Trade",
            "MR Per WR",
            "MR Per LR",
            "Max Cons Loss",
        ],
    )
    return KPI_df.T


# For use in main function
def place_trade(df, ticker, quantity):
    if (
        df["macd"].iloc[-1] > df["signal"].iloc[-1]
        and df["stoch"].iloc[-1] > 30
        and df["stoch"].iloc[-1] > df["stoch"].iloc[-2]
    ):
        app.req_id_event.clear()
        app.reqIds(-1)
        app.req_id_event.wait()
        order_id = app.nextValidOrderId
        app.placeOrder(order_id, getContract(ticker), mktOrder("BUY", quantity))
        pos_df = app.pos_df
        stp_quantity = (
            pos_df[pos_df["Symbol"] == ticker]["Position"]
            .sort_values(ascending=True)
            .values[-1]
        )
        app.placeOrder(
            order_id + 1,
            getContract(ticker),
            stpOrder(
                "SELL",
                stp_quantity,
                round(df["Close"].iloc[-1] - df["atr"].iloc[-1], 2),
            ),
        )


def close_all_open_orders():
    app.reqGlobalCancel()


def close_all_positions():
    ord_id = app.nextValidId
    app.reqPositions()
    pos_df = app.positions_df

    for ticker in pos_df["Symbol"]:
        quantity = pos_df[pos_df["Symbol"] == ticker]["Position"].values[0]
        if quantity > 0:
            app.placeOrder(ord_id, getContract(ticker), mktOrder("SELL", quantity))
        if quantity < 0:
            app.placeOrder(ord_id, getContract(ticker), mktOrder("BUY", abs(quantity)))
        ord_id += 1


def main():

    # Get all positions and open orders
    app.reqPositions()
    pos_df = app.positions_df
    app.reqOpenOrders()
    open_orders_df = app.openOrders_df

    tickers = ["INFY", "TCS", "WIPRO"]
    capital_per_trade = 1000

    ohlcv = deepcopy(
        getHistoricalData(tickers, durationStr="1 M", barSizeSetting="15 mins")
    )
    for ticker in tickers:
        df = ohlcv[ticker]
        ohlcv[ticker]["stoch"] = Stochastic(df)["%K"]
        macd = MACD(ohlcv[ticker])
        ohlcv[ticker]["macd"] = macd["MACD"]
        ohlcv[ticker]["signal"] = macd["Signal"]
        ohlcv[ticker]["atr"] = ATR(ohlcv[ticker], 60)["ATR"]
        ohlcv[ticker].dropna(inplace=True)
        quantity = capital_per_trade / ohlcv[ticker]["Close"].iloc[-1]
        if quantity == 0:
            continue
        # Enter market only if all positions are closed
        if len(pos_df) == 0:
            place_trade(ohlcv[ticker], ticker, quantity)

        # After entering market place only one open position per ticker
        if (len(pos_df) != 0) and ticker not in pos_df["Symbol"].values:
            place_trade(ohlcv[ticker], ticker, quantity)

        # If a position is already closed for the ticker, place another
        if len(pos_df) != 0 and ticker in pos_df["Symbol"].values:
            if pos_df[pos_df["Symbol"] == ticker]["Position"].values[-1] == 0:
                place_trade(ohlcv[ticker], ticker, quantity)

        # Place new stop loss order with new stop loss price
        if pos_df[pos_df["Symbol"] == ticker]["Position"].values[-1] > 0:
            ord_id = open_orders_df[open_orders_df["Symbol"] == ticker][
                "orderId"
            ].values[-1]
            app.cancelOrder(ord_id, "")
            app.req_id_event.clear()
            app.reqIds(-1)
            app.req_id_event.wait()
            order_id = app.nextValidOrderId
            app.placeOrder(
                order_id + 1,
                getContract(ticker),
                stpOrder(
                    "SELL",
                    quantity,
                    round(
                        ohlcv[ticker]["Close"].iloc[-1] - ohlcv[ticker]["atr"].iloc[-1],
                        2,
                    ),
                ),
            )


# tickers = ["INFY", "TCS"]

# strategy = MACD_Stochastic_ATR_Strategy(
#     tickers,
#     secType="STK",
#     currency="INR",
#     exchange="NSE",
#     interval_in_mins=15,
#     backtest=True,
# )

# ohlcv, trade_dat, trade_cou = strategy.backtest()
# kpi = compute_intraday_KPIs(trade_dat, tickers)
# kpi.T.to_csv("kpi.csv")


# tickers = ["INFY", "TCS"]

# strategy = MACD_Stochastic_ATR_Strategy(
#     tickers,
#     secType="STK",
#     currency="INR",
#     exchange="NSE",
#     capital_per_trade=10000,
#     interval_in_mins=15,
#     backtest=False,
# )

tickers = ["AAPL", "MSFT"]

strategy = MACD_Stochastic_ATR_Strategy(
    tickers,
    secType="STK",
    currency="USD",
    exchange="NASDAQ",
    capital_per_trade=1000,
    interval_in_mins=15,
    backtest=False,
)


strategy.run(duration=1)

# Close the connection
event.set()
