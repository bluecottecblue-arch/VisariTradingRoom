-- StrategyForge — Schema Database PostgreSQL

CREATE TABLE IF NOT EXISTS strategy_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'intake',  -- intake | parsed | formalized | bot_generated | backtested | complete
    
    -- Intake originale (JSON raw)
    intake_data JSONB NOT NULL DEFAULT '{}',
    
    -- Output del parser LLM
    structured_strategy JSONB,
    ambiguities JSONB,
    codeable_rules JSONB,
    bias_warnings JSONB,
    completeness_score FLOAT,
    
    -- Risoluzioni ambiguità dell'utente
    user_resolutions JSONB,
    
    -- Specifica formale
    formal_spec JSONB,
    state_machine JSONB,
    parameters JSONB,
    non_optimizable JSONB,
    
    -- Bot generato
    mql5_code TEXT,
    bot_documentation TEXT,
    implementation_assumptions JSONB,
    limitations JSONB,
    
    -- Configurazione backtest
    backtest_config JSONB,
    
    -- Risultati backtest
    backtest_results_insample JSONB,
    backtest_results_oos JSONB,
    walk_forward_results JSONB,
    monte_carlo_results JSONB,
    bias_check_results JSONB,
    
    -- File generati
    report_path VARCHAR(500),
    mql5_file_path VARCHAR(500)
);

-- Indici
CREATE INDEX IF NOT EXISTS idx_sessions_created ON strategy_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON strategy_sessions(status);

-- Tabella per i dati storici cachati
CREATE TABLE IF NOT EXISTS historical_data_cache (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    provider VARCHAR(50) NOT NULL,  -- 'polygon', 'dukascopy', 'local'
    date_from DATE NOT NULL,
    date_to DATE NOT NULL,
    data_quality VARCHAR(20),  -- 'tick', 'bid_ask', 'ohlc_1min', 'ohlc_aggregated'
    file_path VARCHAR(500),
    row_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(symbol, timeframe, provider, date_from, date_to)
);

-- Log delle operazioni per audit
CREATE TABLE IF NOT EXISTS operation_log (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES strategy_sessions(id),
    operation VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- 'success' | 'error' | 'warning'
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
