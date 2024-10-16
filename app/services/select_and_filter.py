import pandas as pd
from typing import List
from datetime import date, datetime
from app.db import schemas
from app.services.data_providers import DataProvider
from app.services.financials_providers import FinancialsProvider
from app.utils.enums import (
    SelectionCriteria,
    ValidationCriteria,
    FilteredLists,
    TradeType,
)
from sqlalchemy.orm import Session


class SelectStocks:
    def __init__(
        self,
        date: date,
        fp: FinancialsProvider,
        streak_list: List[str] = [],
    ):
        self.date = date
        self.streak_list = streak_list
        self.fp = fp
        self.TickerBuckets = {
            SelectionCriteria.NIFTY50_LOW_BY10TO15_FROM_52WH: [],
            SelectionCriteria.NIFTY50_PSUS: [],
            SelectionCriteria.NIFTY50_TOP5_BY_MC: [],
            SelectionCriteria.STREAK_RECOMMENDED: [],
            SelectionCriteria.NEWS_RECOMMENDED: [],
            SelectionCriteria.HIGH_VOL: [],
            SelectionCriteria.HIGH_MOVEMENT: [],
            SelectionCriteria.VOL_SHOCKERS: [],
            FilteredLists.FINAL_LIST: [],
        }

    def update_nifty_50_low_by10to15_from_52wh(
        self, db: Session, fp: FinancialsProvider
    ):
        self.TickerBuckets[SelectionCriteria.NIFTY50_LOW_BY10TO15_FROM_52WH] = (
            fp.get_tickers_from_index(db, "NIFTY50")
        )
        self.TickerBuckets[FilteredLists.FINAL_LIST].extend(
            self.TickerBuckets[SelectionCriteria.NIFTY50_LOW_BY10TO15_FROM_52WH]
        )

    def update_nifty_50_psus(self, db: Session, fp: FinancialsProvider):
        self.TickerBuckets[SelectionCriteria.NIFTY50_PSUS] = (
            fp.get_psu_tickers_from_index(db, "NIFTY50")
        )
        self.TickerBuckets[FilteredLists.FINAL_LIST].extend(
            self.TickerBuckets[SelectionCriteria.NIFTY50_PSUS]
        )

    def update_nifty_50_top5_by_mc(self, db: Session, fp: FinancialsProvider):
        self.TickerBuckets[SelectionCriteria.NIFTY50_TOP5_BY_MC] = (
            fp.get_top_5_by_market_cap(db, "NIFTY50")
        )
        self.TickerBuckets[FilteredLists.FINAL_LIST].extend(
            self.TickerBuckets[SelectionCriteria.NIFTY50_TOP5_BY_MC]
        )

    def update_streak_recommended(self):
        if not self.streak_list:
            return
        self.TickerBuckets[SelectionCriteria.STREAK_RECOMMENDED] = self.streak_list
        self.TickerBuckets[FilteredLists.FINAL_LIST].extend(
            self.TickerBuckets[SelectionCriteria.STREAK_RECOMMENDED]
        )

    def update_news_recommended(self):
        pass

    def update_high_vol(self):
        pass

    def update_high_movement(self):
        pass

    def update_vol_shockers(self):
        pass

    def apply_criteria(
        self,
        db: Session,
        criteria: List[SelectionCriteria],
        fp: FinancialsProvider = None,
    ):
        # Use the default financials provider if not provided
        if not fp:
            fp = self.fp
        if SelectionCriteria.NIFTY50_LOW_BY10TO15_FROM_52WH in criteria:
            self.update_nifty_50_low_by10to15_from_52wh(db, fp)
        if SelectionCriteria.NIFTY50_PSUS in criteria:
            self.update_nifty_50_psus(db, fp)
        if SelectionCriteria.NIFTY50_TOP5_BY_MC in criteria:
            self.update_nifty_50_top5_by_mc(db, fp)
        if SelectionCriteria.STREAK_RECOMMENDED in criteria:
            self.update_streak_recommended()
        if SelectionCriteria.NEWS_RECOMMENDED in criteria:
            self.update_news_recommended()
        if SelectionCriteria.HIGH_VOL in criteria:
            self.update_high_vol()
        if SelectionCriteria.HIGH_MOVEMENT in criteria:
            self.update_high_movement()
        if SelectionCriteria.VOL_SHOCKERS in criteria:
            self.update_vol_shockers()

    def unique_filtered_list(self):
        return list(set(self.TickerBuckets[FilteredLists.FINAL_LIST]))


class StockFilteringService:

    def __init__(
        self,
        dp: DataProvider,
    ):
        self.points_table = []
        self.final_list = []
        self.data_provider = dp

        self.CriteriaWeightage = {
            ValidationCriteria.TREND_INTRADAY: 1,
            ValidationCriteria.TREND_SWING: 1,
            ValidationCriteria.TREND_POSITIONAL: 1,
            ValidationCriteria.TREND_INTR_MATCH_SWING: 2,
            ValidationCriteria.TREND_INTR_MATCH_POS: 2,
            ValidationCriteria.TREND_SWING_MATCH_POS: 3,
            ValidationCriteria.INDEX_TREND: 2,
            ValidationCriteria.GLOBAL_INDEX_TREND: 2,
            ValidationCriteria.MARKET_TREND_NEWS: 2,
            ValidationCriteria.MOMENTUM: 2,
            ValidationCriteria.OPTIONS_INTEREST: 2,
            SelectionCriteria.NIFTY50_LOW_BY10TO15_FROM_52WH: 1,
            SelectionCriteria.NIFTY50_PSUS: 1,
            SelectionCriteria.NIFTY50_TOP5_BY_MC: 1,
            SelectionCriteria.STREAK_RECOMMENDED: 2,
            SelectionCriteria.NEWS_RECOMMENDED: 1,
            SelectionCriteria.HIGH_VOL: 1,
            SelectionCriteria.HIGH_MOVEMENT: 1,
            SelectionCriteria.VOL_SHOCKERS: 1,
        }

    def initialize_criteria_positivity_dict(self, init_value: bool = None):
        return {
            ValidationCriteria.TREND_INTRADAY: init_value,
            ValidationCriteria.TREND_SWING: init_value,
            ValidationCriteria.TREND_POSITIONAL: init_value,
            ValidationCriteria.TREND_INTR_MATCH_SWING: init_value,
            ValidationCriteria.TREND_INTR_MATCH_POS: init_value,
            ValidationCriteria.TREND_SWING_MATCH_POS: init_value,
            ValidationCriteria.INDEX_TREND: init_value,
            ValidationCriteria.GLOBAL_INDEX_TREND: init_value,
            ValidationCriteria.MARKET_TREND_NEWS: init_value,
            ValidationCriteria.MOMENTUM: init_value,
            ValidationCriteria.OPTIONS_INTEREST: init_value,
            SelectionCriteria.NIFTY50_LOW_BY10TO15_FROM_52WH: init_value,
            SelectionCriteria.NIFTY50_PSUS: init_value,
            SelectionCriteria.NIFTY50_TOP5_BY_MC: init_value,
            SelectionCriteria.STREAK_RECOMMENDED: init_value,
            SelectionCriteria.NEWS_RECOMMENDED: init_value,
            SelectionCriteria.HIGH_VOL: init_value,
            SelectionCriteria.HIGH_MOVEMENT: init_value,
            SelectionCriteria.VOL_SHOCKERS: init_value,
        }

    def get_points_table(self):
        return pd.DataFrame(self.points_table)

    def compute_ranked_stocks(
        self,
        db: Session,
        criteria: List[ValidationCriteria],
        stock_list: List[str],
    ):
        data_provider = self.data_provider
        points_table = []
        for ticker in stock_list:
            points = 0
            CriteriaPositivityFalg = self.initialize_criteria_positivity_dict()
            Trend = {
                "Intraday": None,
                "Swing": None,
                "Positional": None,
            }

            if ValidationCriteria.TREND_INTRADAY in criteria:
                if data_provider.get_trend_favorability(
                    db, ticker, trade_type=TradeType.INTRADAY
                ):
                    points += self.CriteriaWeightage[ValidationCriteria.TREND_INTRADAY]
                    CriteriaPositivityFalg[ValidationCriteria.TREND_INTRADAY] = True
                    Trend["Intraday"] = True
                else:
                    CriteriaPositivityFalg[ValidationCriteria.TREND_INTRADAY] = False
                    Trend["Intraday"] = False

            if ValidationCriteria.TREND_SWING in criteria:
                if data_provider.get_trend_favorability(
                    db, ticker, trade_type=TradeType.SWING
                ):
                    points += self.CriteriaWeightage[ValidationCriteria.TREND_SWING]
                    CriteriaPositivityFalg[ValidationCriteria.TREND_SWING] = True
                    Trend["Swing"] = True
                else:
                    CriteriaPositivityFalg[ValidationCriteria.TREND_SWING] = False
                    Trend["Swing"] = False
            if ValidationCriteria.TREND_POSITIONAL in criteria:
                if data_provider.get_trend_favorability(
                    db, ticker, trade_type=TradeType.POSITIONAL
                ):
                    points += self.CriteriaWeightage[
                        ValidationCriteria.TREND_POSITIONAL
                    ]
                    CriteriaPositivityFalg[ValidationCriteria.TREND_POSITIONAL] = True
                    Trend["Positional"] = True
                else:
                    CriteriaPositivityFalg[ValidationCriteria.TREND_POSITIONAL] = False
                    Trend["Positional"] = False

            if ValidationCriteria.TREND_INTR_MATCH_SWING in criteria:
                if Trend["Intraday"] == None:
                    if data_provider.get_trend_favorability(
                        db, ticker, trade_type=TradeType.INTRADAY
                    ):
                        Trend["Intraday"] = True
                    else:
                        Trend["Intraday"] = False

                if Trend["Swing"] == None:
                    if data_provider.get_trend_favorability(
                        db, ticker, trade_type=TradeType.SWING
                    ):
                        Trend["Swing"] = True
                    else:
                        Trend["Swing"] = False

                if Trend["Intraday"] == Trend["Swing"]:
                    points += self.CriteriaWeightage[
                        ValidationCriteria.TREND_INTR_MATCH_SWING
                    ]
                    CriteriaPositivityFalg[
                        ValidationCriteria.TREND_INTR_MATCH_SWING
                    ] = True
                else:
                    CriteriaPositivityFalg[
                        ValidationCriteria.TREND_INTR_MATCH_SWING
                    ] = False
            if ValidationCriteria.TREND_INTR_MATCH_POS in criteria:
                if Trend["Intraday"] == None:
                    if data_provider.get_trend_favorability(
                        db, ticker, trade_type=TradeType.INTRADAY
                    ):
                        Trend["Intraday"] = True
                    else:
                        Trend["Intraday"] = False

                if Trend["Positional"] == None:
                    if data_provider.get_trend_favorability(
                        db, ticker, trade_type=TradeType.POSITIONAL
                    ):
                        Trend["Positional"] = True
                    else:
                        Trend["Positional"] = False

                if Trend["Intraday"] == Trend["Positional"]:
                    points += self.CriteriaWeightage[
                        ValidationCriteria.TREND_INTR_MATCH_POS
                    ]
                    CriteriaPositivityFalg[ValidationCriteria.TREND_INTR_MATCH_POS] = (
                        True
                    )
                else:
                    CriteriaPositivityFalg[ValidationCriteria.TREND_INTR_MATCH_POS] = (
                        False
                    )
            if ValidationCriteria.TREND_SWING_MATCH_POS in criteria:
                if Trend["Swing"] == None:
                    if data_provider.get_trend_favorability(
                        db, ticker, trade_type=TradeType.SWING
                    ):
                        Trend["Swing"] = True
                    else:
                        Trend["Swing"] = False

                if Trend["Positional"] == None:
                    if data_provider.get_trend_favorability(
                        db, ticker, trade_type=TradeType.POSITIONAL
                    ):
                        Trend["Positional"] = True
                    else:
                        Trend["Positional"] = False

                if Trend["Swing"] == Trend["Positional"]:
                    points += self.CriteriaWeightage[
                        ValidationCriteria.TREND_SWING_MATCH_POS
                    ]
                    CriteriaPositivityFalg[ValidationCriteria.TREND_SWING_MATCH_POS] = (
                        True
                    )
                else:
                    CriteriaPositivityFalg[ValidationCriteria.TREND_SWING_MATCH_POS] = (
                        False
                    )
            if ValidationCriteria.INDEX_TREND in criteria:
                if data_provider.get_index_trend_favorability(db, ticker):
                    points += self.CriteriaWeightage[ValidationCriteria.INDEX_TREND]
                    CriteriaPositivityFalg[ValidationCriteria.INDEX_TREND] = True
                else:
                    CriteriaPositivityFalg[ValidationCriteria.INDEX_TREND] = False
            if ValidationCriteria.GLOBAL_INDEX_TREND in criteria:
                if data_provider.get_global_index_trend_favorability(db, ticker):
                    points += self.CriteriaWeightage[
                        ValidationCriteria.GLOBAL_INDEX_TREND
                    ]
                    CriteriaPositivityFalg[ValidationCriteria.GLOBAL_INDEX_TREND] = True
                else:
                    CriteriaPositivityFalg[ValidationCriteria.GLOBAL_INDEX_TREND] = (
                        False
                    )
            if ValidationCriteria.MARKET_TREND_NEWS in criteria:
                if data_provider.get_market_trend_news_favorability(db, ticker):
                    points += self.CriteriaWeightage[
                        ValidationCriteria.MARKET_TREND_NEWS
                    ]
                    CriteriaPositivityFalg[ValidationCriteria.MARKET_TREND_NEWS] = True
                else:
                    CriteriaPositivityFalg[ValidationCriteria.MARKET_TREND_NEWS] = False
            if ValidationCriteria.MOMENTUM in criteria:
                if data_provider.get_momentum_favorability(db, ticker):
                    points += self.CriteriaWeightage[ValidationCriteria.MOMENTUM]
                    CriteriaPositivityFalg[ValidationCriteria.MOMENTUM] = True
                else:
                    CriteriaPositivityFalg[ValidationCriteria.MOMENTUM] = False
            if ValidationCriteria.OPTIONS_INTEREST in criteria:
                if data_provider.get_options_interest_favorablitiy(db, ticker):
                    points += self.CriteriaWeightage[
                        ValidationCriteria.OPTIONS_INTEREST
                    ]
                    CriteriaPositivityFalg[ValidationCriteria.OPTIONS_INTEREST] = True
                else:
                    CriteriaPositivityFalg[ValidationCriteria.OPTIONS_INTEREST] = False

            points_table.append(
                {
                    "Ticker": ticker,
                    "Points": points,
                    "TrendIntraday": CriteriaPositivityFalg[
                        ValidationCriteria.TREND_INTRADAY
                    ],
                    "TrendSwing": CriteriaPositivityFalg[
                        ValidationCriteria.TREND_SWING
                    ],
                    "TrendPositional": CriteriaPositivityFalg[
                        ValidationCriteria.TREND_POSITIONAL
                    ],
                    "TrendIntradayMatchSwing": CriteriaPositivityFalg[
                        ValidationCriteria.TREND_INTR_MATCH_SWING
                    ],
                    "TrendIntradayMatchPos": CriteriaPositivityFalg[
                        ValidationCriteria.TREND_INTR_MATCH_POS
                    ],
                    "TrendSwingMatchPos": CriteriaPositivityFalg[
                        ValidationCriteria.TREND_SWING_MATCH_POS
                    ],
                    "IndexTrend": CriteriaPositivityFalg[
                        ValidationCriteria.INDEX_TREND
                    ],
                    "GlobalIndexTrend": CriteriaPositivityFalg[
                        ValidationCriteria.GLOBAL_INDEX_TREND
                    ],
                    "MarketTrendNews": CriteriaPositivityFalg[
                        ValidationCriteria.MARKET_TREND_NEWS
                    ],
                    "Momentum": CriteriaPositivityFalg[ValidationCriteria.MOMENTUM],
                    "OptionsInterest": CriteriaPositivityFalg[
                        ValidationCriteria.OPTIONS_INTEREST
                    ],
                }
            )

        points_table_df = pd.DataFrame(points_table)
        points_table_df.sort_values(by="Points", ascending=False, inplace=True)
        return points_table_df
