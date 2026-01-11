# settings.py

APP_NAME = "WorldMarketReviewer"

# Risk thresholds (fully adjustable)
VOL_RISK_OFF = 0.30
DRAWDOWN_RISK_OFF = -0.35

# Exposure levels
EXPOSURE_RISK_ON = 1.0
EXPOSURE_RISK_OFF = 0.25
EXPOSURE_KILL = 0.0

# Storage
DB_FILE = "state.db"

# Scheduler
RUN_EVERY_SECONDS = 3600  # run once per hour

# Debug
DEBUG = True
