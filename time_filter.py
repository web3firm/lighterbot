"""
Time-of-Day Trading Filter

Avoids trading during low liquidity hours (3am-6am UTC).
Institutions know that spreads widen and volatility spikes during these hours.
"""

from datetime import datetime
from config import settings
from logger import get_logger

logger = get_logger()


def is_trading_hours() -> tuple[bool, str]:
    """
    Check if current time is within allowed trading hours
    
    Returns:
        (allowed, reason) - True if trading allowed
    """
    
    if not settings.enable_time_filter:
        return True, "Time filter disabled"
    
    current_hour_utc = datetime.utcnow().hour
    
    # Trading hours: 6am - 3am UTC (avoids 3am-6am low liquidity)
    start_hour = settings.trading_hours_start  # 6
    end_hour = settings.trading_hours_end  # 3 (next day)
    
    # Handle wrap-around (end_hour < start_hour means trading continues past midnight)
    if end_hour < start_hour:
        # Trading allowed from start_hour to 23:59, then 00:00 to end_hour
        if current_hour_utc >= start_hour or current_hour_utc < end_hour:
            return True, f"Trading hours active (UTC {current_hour_utc:02d}:xx)"
        else:
            return False, f"Low liquidity hours (UTC {current_hour_utc:02d}:xx, trade from {start_hour:02d}-{end_hour:02d})"
    else:
        # Normal range (start < end)
        if start_hour <= current_hour_utc < end_hour:
            return True, f"Trading hours active (UTC {current_hour_utc:02d}:xx)"
        else:
            return False, f"Outside trading hours (UTC {current_hour_utc:02d}:xx, trade {start_hour:02d}-{end_hour:02d})"


def get_trading_session() -> str:
    """
    Identify current trading session
    
    Returns:
        Session name: 'Asia', 'Europe', 'US', 'Low Liquidity'
    """
    
    current_hour_utc = datetime.utcnow().hour
    
    # Asia session: 00:00 - 08:00 UTC
    if 0 <= current_hour_utc < 8:
        if 3 <= current_hour_utc < 6:
            return "Low Liquidity (Asia Close)"
        return "Asia Session"
    
    # Europe session: 08:00 - 16:00 UTC
    elif 8 <= current_hour_utc < 16:
        return "Europe Session"
    
    # US session: 16:00 - 00:00 UTC
    else:
        return "US Session"


def should_reduce_size_for_time() -> tuple[bool, float]:
    """
    Check if position size should be reduced due to time
    
    Returns:
        (should_reduce, multiplier) - multiplier is 0.5-1.0
    """
    
    session = get_trading_session()
    
    # Reduce size during Asia close (low liquidity)
    if "Low Liquidity" in session:
        return True, 0.5
    
    # Full size during major sessions
    return False, 1.0
