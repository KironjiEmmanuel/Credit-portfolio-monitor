"""
Tunable assumptions for the synthetic loan-book generator.

Everything here is ILLUSTRATIVE. The numbers are chosen to look like a typical
small-ticket, daily-repayment credit lender - they are not calibrated to, or
derived from, any real institution's data.
"""
from datetime import date

SEED = 42

# --- timeline -----------------------------------------------------------------
END_DATE = date(2026, 9, 18)   # last snapshot date
N_SNAPSHOTS = 30               # one export per day, ending on END_DATE
BURN_IN_DAYS = 430             # simulate this long before the first snapshot so the book has mature loans

# --- origination --------------------------------------------------------------
DAILY_ORIGINATIONS_START = 9.0     # mean new loans/day at start of burn-in
DAILY_ORIGINATIONS_END = 13.5      # mean new loans/day at END_DATE (book is growing)
SUNDAY_FACTOR = 0.25               # fewer disbursements on Sundays
REPEAT_BORROWER_SHARE = 0.08       # share of new loans taken by an existing member

# --- organisation -------------------------------------------------------------
BRANCHES = [f"{i:03d}" for i in range(1, 13)] + ["HQ"]
N_CHAMPIONS = 18
N_TEAMS = 6
CHAMPION_HOME_BRANCH_SHARE = 0.85  # share of a champion's loans booked in their home branch

# --- loan terms ---------------------------------------------------------------
# Terms are multiples of 31 days; tracking fee accrues at a flat KES/day of term.
TERMS = [31, 62, 93, 124, 186, 248, 310, 365]
TRACKING_FEE_PER_DAY = 25.0

# code, display name, weight, median amount (KES), daily flat rate, term weights, risk multiplier
PRODUCTS = [
    ("KIOSKSTOCK", "Kiosk Stock Purchase",   0.24, 28_000, 0.00200, [0.05, 0.30, 0.35, 0.20, 0.06, 0.03, 0.01, 0.00], 1.00),
    ("WORKCAP",    "Working Capital",        0.20, 45_000, 0.00180, [0.02, 0.15, 0.30, 0.28, 0.15, 0.07, 0.02, 0.01], 1.05),
    ("MEDICAL",    "Medical Bills",          0.12, 20_000, 0.00240, [0.03, 0.20, 0.30, 0.30, 0.12, 0.04, 0.01, 0.00], 1.20),
    ("SCHOOLFEES", "School Fees",            0.11, 32_000, 0.00160, [0.01, 0.08, 0.20, 0.32, 0.25, 0.10, 0.03, 0.01], 0.85),
    ("ASSETREPAIR","Asset Repair",           0.10, 15_000, 0.00220, [0.10, 0.35, 0.30, 0.15, 0.06, 0.03, 0.01, 0.00], 1.10),
    ("EMERGENCY",  "Emergency Cash",         0.10, 10_000, 0.00260, [0.25, 0.45, 0.20, 0.07, 0.02, 0.01, 0.00, 0.00], 1.45),
    ("BIZEXP",     "Business Expansion",     0.08, 80_000, 0.00150, [0.00, 0.04, 0.10, 0.20, 0.30, 0.22, 0.10, 0.04], 0.95),
    ("ASSETFIN",   "Asset Finance",          0.05,120_000, 0.00120, [0.00, 0.00, 0.03, 0.08, 0.20, 0.30, 0.25, 0.14], 0.75),
]
AMOUNT_SIGMA = 0.55                # lognormal spread of approved amounts
AMOUNT_MIN, AMOUNT_MAX = 5_000, 250_000

# security (collateral) value as a multiple of the approved amount: lognormal(mu, sigma)
COLLATERAL_MU, COLLATERAL_SIGMA, COLLATERAL_FLOOR = 0.75, 0.45, 0.35

ASSET_TYPES = [("Motorbike", 0.82), ("Vehicle", 0.10), ("Equipment", 0.08)]

# --- repayment behaviour ------------------------------------------------------
# Borrower types. P(defaulter) is scaled by product risk and by a per-champion multiplier.
P_DEFAULTER_BASE = 0.075
P_SHAKY_BASE = 0.14
CHAMPION_QUALITY_SIGMA = 0.45      # lognormal spread of champion default multipliers
DAILY_PAY_PROB = {"good": 0.985, "shaky": 0.78, "defaulter_after_stop": 0.02}
DAILY_CATCHUP_PROB = {"good": 0.55, "shaky": 0.35, "defaulter_after_stop": 0.0}
DEFAULT_STOP_FRACTION = (0.05, 0.90)   # a defaulter stops paying somewhere in this fraction of the term
WRITE_OFF_MEAN_DAYS = 230              # mean days a defaulted loan lingers in the active file after it stops paying
REPO_PROB_FIRST, REPO_PROB_SECOND = 0.35, 0.25
REPO_FEE = 1_500
PENALTY_RATE_PER_ARREARS_DAY = 0.05    # x installment, per day in arrears beyond the first
CHAMPION_BOOK_SIGMA = 0.85         # lognormal spread of champion book sizes (drives concentration)
