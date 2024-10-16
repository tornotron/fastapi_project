from unittest.mock import MagicMock
import pytest
from app.lib import Yahoo as yh
import pandas as pd

# Constants for testing
PREV_YEARS_TO_CONSIDER_FCF = [0]  # put atleast [0] or maximum [0,-1,-2] years
PREV_YEARS_TO_CONSIDER_OCF = [0]  # put atleast [0] or maximum [0,-1,-2] years
PREV_YEARS_TO_CONSIDER_ROCE = [0]  # put atleast [0] or maximum [0,-1,-2] years
PREV_YEARS_TO_CONSIDER_ROE = [0]  # put atleast [0] or maximum [0,-1,-2] years
PREV_YEARS_TO_CONSIDER_D2E = [0]  # put atleast [0] or maximum [0,-1,-2] years
PREV_YEARS_TO_CONSIDER_CR = [0]  # put atleast [0] or maximum [0,-1,-2] years
PREV_YEARS_TO_CONSIDER_PS = [0]  # put atleast [0] or maximum [0,-1,-2] years
PREV_YEARS_TO_CONSIDER_SG_1YR = [0]  # put atleast [0] or maximum [0,-1,-2] years
PREV_YEARS_TO_CONSIDER_SG_3YR = [0]  # put atleast [0] or maximum [0,-1,-2] years
PREV_YEARS_TO_CONSIDER_PG_1YR = [0]  # put atleast [0] or maximum [0,-1,-2] years
PREV_YEARS_TO_CONSIDER_PG_3YR = [0]  # put atleast [0] or maximum [0,-1,-2] years
INDUSTRY_PE = 20
INDEX_PE = 20
USE_INDEX_PE = False
PREV_QUARTERS_TO_CONSIDER_FOR_POSITIVE_SG = [
    0
]  # put atleast [0] or maximum [0,-1,-2] quarters
PREV_QUARTERS_TO_CONSIDER_FOR_POSITIVE_PG = [
    0
]  # put atleast [0] or maximum [0,-1,-2] quarters
PREV_QUARTERS_TO_CONSIDER_FOR_POSITIVE_OP_PG = [
    0
]  # put atleast [0] or maximum [0,-1,-2] quarters

company = yh.Yahoo("AAPL")


def test_calculate_free_cash_flow():
    assert company.calculate_free_cash_flow(0) == 99584000000.0
