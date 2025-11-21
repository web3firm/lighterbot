-- LighterBot PostgreSQL Database Schema
-- 7 tables for comprehensive trade tracking and analytics

-- Table 1: Trades - Complete trade history
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(100) UNIQUE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    exit_price NUMERIC(20, 8),
    size NUMERIC(20, 8) NOT NULL,
    leverage INTEGER NOT NULL,
    pnl_usd NUMERIC(20, 8),
    pnl_pct NUMERIC(10, 4),
    fees_usd NUMERIC(20, 8),
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    duration_seconds INTEGER,
    exit_reason VARCHAR(100),
    indicators JSONB,
    ml_prediction INTEGER,
    ml_confidence NUMERIC(5, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 2: Signals - All strategy signals (taken or not)
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    signal_id VARCHAR(100) UNIQUE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    sl_price NUMERIC(20, 8) NOT NULL,
    tp_price NUMERIC(20, 8) NOT NULL,
    size NUMERIC(20, 8) NOT NULL,
    leverage INTEGER NOT NULL,
    signal_strength INTEGER NOT NULL,
    confidence NUMERIC(5, 4) NOT NULL,
    indicators JSONB,
    was_taken BOOLEAN DEFAULT FALSE,
    rejection_reason VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 3: ML Predictions - ML model predictions per trade
CREATE TABLE IF NOT EXISTS ml_predictions (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(100) REFERENCES trades(trade_id),
    model_version VARCHAR(50) NOT NULL,
    prediction INTEGER NOT NULL,
    probability NUMERIC(5, 4) NOT NULL,
    confidence VARCHAR(20) NOT NULL,
    features JSONB NOT NULL,
    actual_outcome INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 4: Positions - Real-time position tracking
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    position_id VARCHAR(100) UNIQUE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    current_price NUMERIC(20, 8) NOT NULL,
    size NUMERIC(20, 8) NOT NULL,
    leverage INTEGER NOT NULL,
    unrealized_pnl NUMERIC(20, 8) NOT NULL,
    liquidation_price NUMERIC(20, 8),
    status VARCHAR(20) NOT NULL,
    opened_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 5: Funding Payments - Track funding rate payments
CREATE TABLE IF NOT EXISTS funding_payments (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    payment_usd NUMERIC(20, 8) NOT NULL,
    funding_rate NUMERIC(10, 8) NOT NULL,
    position_size NUMERIC(20, 8) NOT NULL,
    payment_time TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 6: Performance Metrics - Daily performance snapshots
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    starting_balance NUMERIC(20, 8) NOT NULL,
    ending_balance NUMERIC(20, 8) NOT NULL,
    daily_pnl NUMERIC(20, 8) NOT NULL,
    daily_pnl_pct NUMERIC(10, 4) NOT NULL,
    total_trades INTEGER NOT NULL,
    winning_trades INTEGER NOT NULL,
    losing_trades INTEGER NOT NULL,
    win_rate NUMERIC(5, 4) NOT NULL,
    avg_win NUMERIC(20, 8),
    avg_loss NUMERIC(20, 8),
    largest_win NUMERIC(20, 8),
    largest_loss NUMERIC(20, 8),
    total_fees NUMERIC(20, 8),
    sharpe_ratio NUMERIC(10, 4),
    max_drawdown_pct NUMERIC(10, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 7: Bot State - Bot operational state
CREATE TABLE IF NOT EXISTS bot_state (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals(created_at);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_performance_date ON performance_metrics(date);

-- Triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_trades_updated_at BEFORE UPDATE ON trades
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_positions_updated_at BEFORE UPDATE ON positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_bot_state_updated_at BEFORE UPDATE ON bot_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
