# -*- coding: utf-8 -*-
"""
Homework Solution - Backtesting template for TI based Strategies (intraday KPI)

@author: Mayank Rasu (http://rasuquant.com/wp/)
"""

# Import libraries
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import pandas as pd
import threading
import time
import numpy as np
from copy import deepcopy


class TradeApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.data = {}
        self.historic_data_event = threading.Event()

    def historicalData(self, reqId, bar):
        if reqId not in self.data:
            self.data[reqId] = pd.DataFrame(
                [
                    {
                        "Date": bar.date,
                        "Open": bar.open,
                        "High": bar.high,
                        "Low": bar.low,
                        "Close": bar.close,
                        "Volume": bar.volume,
                    }
                ]
            )
        else:
            self.data[reqId] = pd.concat(
                (
                    self.data[reqId],
                    pd.DataFrame(
                        [
                            {
                                "Date": bar.date,
                                "Open": bar.open,
                                "High": bar.high,
                                "Low": bar.low,
                                "Close": bar.close,
                                "Volume": bar.volume,
                            }
                        ]
                    ),
                )
            )
            # self.data[reqId].append({"Date":bar.date,"Open":bar.open,"High":bar.high,"Low":bar.low,"Close":bar.close,"Volume":bar.volume})
        print(
            "reqID:{}, date:{}, open:{}, high:{}, low:{}, close:{}, volume:{}".format(
                reqId, bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume
            )
        )

    def historicalDataEnd(self, reqId, start, end):
        self.historic_data_event.set()


def usTechStk(symbol, sec_type="STK", currency="USD", exchange="ISLAND"):
    contract = Contract()
    contract.symbol = symbol
    contract.secType = sec_type
    contract.currency = currency
    contract.exchange = exchange
    return contract


def histData(req_num, contract, duration, candle_size):
    """extracts historical data"""
    app.historic_data_event.clear()
    app.reqHistoricalData(
        reqId=req_num,
        contract=contract,
        endDateTime="",
        durationStr=duration,
        barSizeSetting=candle_size,
        whatToShow="ADJUSTED_LAST",
        useRTH=1,
        formatDate=1,
        keepUpToDate=0,
        chartOptions=[],
    )  # EClient function to request contract details
    app.historic_data_event.wait()  # wait until data is received


def websocket_con():
    app.run()


app = TradeApp()
app.connect(
    host="127.0.0.1", port=7497, clientId=23
)  # port 4002 for ib gateway paper trading/7497 for TWS paper trading
con_thread = threading.Thread(target=websocket_con, daemon=True)
con_thread.start()
time.sleep(1)  # some latency added to ensure that the connection is established

# tickers = [
#     "FB",
#     "AMZN",
#     "INTC",
#     "MSFT",
#     "AAPL",
#     "GOOG",
#     "CSCO",
#     "CMCSA",
#     "ADBE",
#     "NVDA",
#     "NFLX",
#     "PYPL",
#     "AMGN",
#     "AVGO",
#     "TXN",
#     "CHTR",
#     "QCOM",
#     "GILD",
#     "FISV",
#     "BKNG",
#     "INTU",
#     "ADP",
#     "CME",
#     "TMUS",
#     "MU",
# ]

tickers = ["INFY", "TCS"]

for ticker in tickers:
    histData(tickers.index(ticker), usTechStk(ticker), "1 Y", "15 mins")


###################storing trade app object in dataframe#######################
def dataDataframe(symbols, TradeApp_obj):
    "returns extracted historical data in dataframe format"
    df_data = {}
    for symbol in symbols:
        df_data[symbol] = pd.DataFrame(TradeApp_obj.data[symbols.index(symbol)])
        df_data[symbol].set_index("Date", inplace=True)
    return df_data


################################################################################


def MACD(DF, a=12, b=26, c=9):
    """function to calculate MACD
    typical values a(fast moving average) = 12;
                   b(slow moving average) =26;
                   c(signal line ma window) =9"""
    df = DF.copy()
    df["MA_Fast"] = df["Close"].ewm(span=a, min_periods=a).mean()
    df["MA_Slow"] = df["Close"].ewm(span=b, min_periods=b).mean()
    df["MACD"] = df["MA_Fast"] - df["MA_Slow"]
    df["Signal"] = df["MACD"].ewm(span=c, min_periods=c).mean()
    df.dropna(inplace=True)
    return df


def stochOscltr(DF, a=20, b=3):
    """function to calculate Stochastics
    a = lookback period
    b = moving average window for %D"""
    df = DF.copy()
    df["C-L"] = df["Close"] - df["Low"].rolling(a).min()
    df["H-L"] = df["High"].rolling(a).max() - df["Low"].rolling(a).min()
    df["%K"] = df["C-L"] / df["H-L"] * 100
    # df['%D'] = df['%K'].ewm(span=b,min_periods=b).mean()
    return df["%K"].rolling(b).mean()


def atr(DF, n):
    "function to calculate True Range and Average True Range"
    df = DF.copy()
    df["H-L"] = abs(df["High"] - df["Low"])
    df["H-PC"] = abs(df["High"] - df["Close"].shift(1))
    df["L-PC"] = abs(df["Low"] - df["Close"].shift(1))
    df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1, skipna=False)
    # df['ATR'] = df['TR'].rolling(n).mean()
    df["ATR"] = df["TR"].ewm(com=n, min_periods=n).mean()
    return df["ATR"]


def winRate(DF):
    "function to calculate win rate of intraday trading strategy"
    df = DF["return"]
    pos = df[df > 1]
    neg = df[df < 1]
    return (len(pos) / len(pos + neg)) * 100


def meanretpertrade(DF):
    df = DF["return"]
    df_temp = (df - 1).dropna()
    return df_temp[df_temp != 0].mean()


def meanretwintrade(DF):
    df = DF["return"]
    df_temp = (df - 1).dropna()
    return df_temp[df_temp > 0].mean()


def meanretlostrade(DF):
    df = DF["return"]
    df_temp = (df - 1).dropna()
    return df_temp[df_temp < 0].mean()


def maxconsectvloss(DF):
    df = DF["return"]
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


# extract and store historical data in dataframe
historicalData = dataDataframe(tickers, app)

##############################backtesting########################################

ohlc_dict = deepcopy(historicalData)
tickers_signal = {}
tickers_ret = {}
trade_count = {}
trade_data = {}
for ticker in tickers:
    print("Calculating MACD & Stochastics for ", ticker)
    ohlc_dict[ticker]["stoch"] = stochOscltr(ohlc_dict[ticker])
    ohlc_dict[ticker]["macd"] = MACD(ohlc_dict[ticker])["MACD"]
    ohlc_dict[ticker]["signal"] = MACD(ohlc_dict[ticker])["Signal"]
    ohlc_dict[ticker]["atr"] = atr(ohlc_dict[ticker], 60)
    ohlc_dict[ticker].dropna(inplace=True)
    trade_count[ticker] = 0
    tickers_signal[ticker] = ""
    tickers_ret[ticker] = [0]
    trade_data[ticker] = {}


# Identifying Signals and calculating daily return (Stop Loss factored in)
for ticker in tickers:
    print("Calculating daily returns for ", ticker)
    for i in range(1, len(ohlc_dict[ticker])):
        if tickers_signal[ticker] == "":
            tickers_ret[ticker].append(0)
            if (
                ohlc_dict[ticker]["macd"].iloc[i] > ohlc_dict[ticker]["signal"].iloc[i]
                and ohlc_dict[ticker]["stoch"].iloc[i] > 30
                and ohlc_dict[ticker]["stoch"].iloc[i]
                > ohlc_dict[ticker]["stoch"].iloc[i - 1]
            ):
                tickers_signal[ticker] = "Buy"
                trade_count[ticker] += 1
                trade_data[ticker][trade_count[ticker]] = [
                    ohlc_dict[ticker]["Close"].iloc[i]
                ]

        elif tickers_signal[ticker] == "Buy":
            if (
                ohlc_dict[ticker]["Low"].iloc[i]
                < ohlc_dict[ticker]["Close"].iloc[i - 1]
                - ohlc_dict[ticker]["atr"].iloc[i - 1]
            ):
                tickers_signal[ticker] = ""
                trade_data[ticker][trade_count[ticker]].append(
                    ohlc_dict[ticker]["Close"].iloc[i - 1]
                    - ohlc_dict[ticker]["atr"].iloc[i - 1]
                )
                trade_count[ticker] += 1
                tickers_ret[ticker].append(
                    (
                        (
                            ohlc_dict[ticker]["Close"].iloc[i - 1]
                            - ohlc_dict[ticker]["atr"].iloc[i - 1]
                        )
                        / ohlc_dict[ticker]["Close"].iloc[i - 1]
                    )
                    - 1
                )
            else:
                tickers_ret[ticker].append(
                    (
                        ohlc_dict[ticker]["Close"].iloc[i]
                        / ohlc_dict[ticker]["Close"].iloc[i - 1]
                    )
                    - 1
                )

    if trade_count[ticker] % 2 != 0:
        trade_data[ticker][trade_count[ticker]].append(
            ohlc_dict[ticker]["Close"].iloc[i]
        )

    ohlc_dict[ticker]["ret"] = np.array(tickers_ret[ticker])


# calculating overall strategy's KPIs
trade_df = {}
for ticker in tickers:
    trade_df[ticker] = pd.DataFrame(trade_data[ticker]).T
    trade_df[ticker].columns = ["trade_entry_pr", "trade_exit_pr"]
    trade_df[ticker]["return"] = (
        trade_df[ticker]["trade_exit_pr"] / trade_df[ticker]["trade_entry_pr"]
    )


# calculating individual stock's KPIs
win_rate = {}
mean_ret_pt = {}
mean_ret_pwt = {}
mean_ret_plt = {}
max_cons_loss = {}
for ticker in tickers:
    print("calculating intraday KPIs for ", ticker)
    win_rate[ticker] = winRate(trade_df[ticker])
    mean_ret_pt[ticker] = meanretpertrade(trade_df[ticker])
    mean_ret_pwt[ticker] = meanretwintrade(trade_df[ticker])
    mean_ret_plt[ticker] = meanretlostrade(trade_df[ticker])
    max_cons_loss[ticker] = maxconsectvloss(trade_df[ticker])

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
KPI_df.T
KPI_df.T.to_csv("manyak_intraday_kpi.csv")
