"""
Prometheus Metrics Exporter for Trading Bot
Exposes metrics on http://localhost:9090/metrics
"""
from prometheus_client import Counter, Histogram, Gauge, Info, start_http_server
from typing import Dict, Any
from logger import logger


class BotMetrics:
    """
    Export trading bot metrics to Prometheus
    
    Visualize in Grafana with queries like:
    - rate(bot_trades_total[5m]) - Trades per second
    - bot_pnl_total - Current PnL
    - histogram_quantile(0.95, bot_api_latency_seconds) - 95th percentile latency
    """
    
    def __init__(self, port: int = 9090):
        self.port = port
        
        # Trading Metrics
        self.trades_total = Counter(
            'bot_trades_total',
            'Total number of trades executed',
            ['side', 'strategy', 'market']
        )
        
        self.pnl_total = Gauge(
            'bot_pnl_total_usd',
            'Total profit/loss in USD'
        )
        
        self.pnl_unrealized = Gauge(
            'bot_pnl_unrealized_usd',
            'Unrealized PnL in USD',
            ['market']
        )
        
        self.position_size = Gauge(
            'bot_position_size',
            'Current position size in base units',
            ['market', 'side']
        )
        
        self.account_balance = Gauge(
            'bot_account_balance_usd',
            'Total account balance in USD'
        )
        
        # Strategy Metrics
        self.strategy_signals = Counter(
            'bot_strategy_signals_total',
            'Strategy signals generated',
            ['strategy', 'signal_type']
        )
        
        self.strategy_win_rate = Gauge(
            'bot_strategy_win_rate',
            'Strategy win rate (0-1)',
            ['strategy']
        )
        
        # Performance Metrics
        self.api_latency = Histogram(
            'bot_api_latency_seconds',
            'API call latency in seconds',
            ['endpoint', 'method'],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )
        
        self.execution_latency = Histogram(
            'bot_execution_latency_seconds',
            'Trade execution latency',
            buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
        )
        
        # Risk Metrics
        self.portfolio_heat = Gauge(
            'bot_portfolio_heat_ratio',
            'Portfolio heat (risk exposure) ratio'
        )
        
        self.drawdown_current = Gauge(
            'bot_drawdown_current',
            'Current drawdown percentage'
        )
        
        self.drawdown_max_daily = Gauge(
            'bot_drawdown_max_daily',
            'Maximum drawdown today'
        )
        
        self.kelly_fraction = Gauge(
            'bot_kelly_fraction',
            'Current Kelly Criterion fraction'
        )
        
        # Market Metrics
        self.market_price = Gauge(
            'bot_market_price_usd',
            'Current market price',
            ['market', 'symbol']
        )
        
        self.market_spread_bps = Gauge(
            'bot_market_spread_basis_points',
            'Market spread in basis points',
            ['market']
        )
        
        # System Metrics
        self.uptime_seconds = Gauge(
            'bot_uptime_seconds',
            'Bot uptime in seconds'
        )
        
        self.errors_total = Counter(
            'bot_errors_total',
            'Total errors encountered',
            ['error_type', 'component']
        )
        
        self.circuit_breaker_state = Gauge(
            'bot_circuit_breaker_open',
            'Circuit breaker state (1=open, 0=closed)',
            ['service']
        )
        
        # Bot Info
        self.bot_info = Info(
            'bot_info',
            'Bot configuration and version'
        )
        
        self._server_started = False
        
        logger.info(f"Metrics initialized (will serve on port {port})")
    
    def start_server(self):
        """Start Prometheus metrics HTTP server"""
        if not self._server_started:
            try:
                start_http_server(self.port)
                self._server_started = True
                logger.info(f"✓ Prometheus metrics server started on http://localhost:{self.port}/metrics")
            except Exception as e:
                logger.error(f"Failed to start metrics server: {e}")
    
    # Trading Metrics
    def record_trade(self, side: str, strategy: str, market: str, pnl: float = 0):
        """Record a trade execution"""
        self.trades_total.labels(side=side, strategy=strategy, market=market).inc()
        if pnl != 0:
            self.pnl_total.inc(pnl)
    
    def set_account_balance(self, balance: float):
        """Update account balance"""
        self.account_balance.set(balance)
    
    def set_position(self, market: str, side: str, size: float):
        """Update position size"""
        self.position_size.labels(market=market, side=side).set(size)
    
    def set_unrealized_pnl(self, market: str, pnl: float):
        """Update unrealized PnL"""
        self.pnl_unrealized.labels(market=market).set(pnl)
    
    # Strategy Metrics
    def record_signal(self, strategy: str, signal_type: str):
        """Record a strategy signal"""
        self.strategy_signals.labels(strategy=strategy, signal_type=signal_type).inc()
    
    def set_strategy_win_rate(self, strategy: str, win_rate: float):
        """Update strategy win rate"""
        self.strategy_win_rate.labels(strategy=strategy).set(win_rate)
    
    # Performance Metrics
    def record_api_call(self, endpoint: str, method: str, duration: float):
        """Record API call latency"""
        self.api_latency.labels(endpoint=endpoint, method=method).observe(duration)
    
    def record_execution(self, duration: float):
        """Record trade execution latency"""
        self.execution_latency.observe(duration)
    
    # Risk Metrics
    def set_risk_metrics(self, metrics: Dict[str, float]):
        """Update risk metrics"""
        if 'portfolio_heat' in metrics:
            self.portfolio_heat.set(metrics['portfolio_heat'])
        if 'daily_drawdown' in metrics:
            self.drawdown_current.set(metrics['daily_drawdown'])
        if 'max_drawdown_today' in metrics:
            self.drawdown_max_daily.set(metrics['max_drawdown_today'])
        if 'kelly_fraction' in metrics:
            self.kelly_fraction.set(metrics['kelly_fraction'])
    
    # Market Metrics
    def set_market_price(self, market: str, symbol: str, price: float):
        """Update market price"""
        self.market_price.labels(market=market, symbol=symbol).set(price)
    
    def set_market_spread(self, market: str, spread_bps: float):
        """Update market spread"""
        self.market_spread_bps.labels(market=market).set(spread_bps)
    
    # System Metrics
    def set_uptime(self, seconds: float):
        """Update bot uptime"""
        self.uptime_seconds.set(seconds)
    
    def record_error(self, error_type: str, component: str):
        """Record an error"""
        self.errors_total.labels(error_type=error_type, component=component).inc()
    
    def set_circuit_breaker(self, service: str, is_open: bool):
        """Update circuit breaker state"""
        self.circuit_breaker_state.labels(service=service).set(1 if is_open else 0)
    
    def set_bot_info(self, info: Dict[str, str]):
        """Set bot configuration info"""
        self.bot_info.info(info)


# Global metrics instance
bot_metrics = BotMetrics()
