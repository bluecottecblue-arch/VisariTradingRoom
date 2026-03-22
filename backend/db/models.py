"""
ORM Models — solo caricati se SQLAlchemy è disponibile
"""
try:
    from sqlalchemy import Column, String, Float, Integer, Text, DateTime, JSON
    from sqlalchemy.sql import func
    from db.database import Base

    class StrategySession(Base):
        __tablename__ = "strategy_sessions"

        id = Column(String, primary_key=True)
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), onupdate=func.now())
        status = Column(String, default="intake")
        intake_data = Column(JSON, default={})
        structured_strategy = Column(JSON)
        ambiguities = Column(JSON)
        codeable_rules = Column(JSON)
        bias_warnings = Column(JSON)
        completeness_score = Column(Float)
        user_resolutions = Column(JSON)
        formal_spec = Column(JSON)
        state_machine = Column(JSON)
        parameters = Column(JSON)
        non_optimizable = Column(JSON)
        mql5_code = Column(Text)
        bot_documentation = Column(Text)
        implementation_assumptions = Column(JSON)
        limitations = Column(JSON)
        backtest_config = Column(JSON)
        backtest_results_insample = Column(JSON)
        backtest_results_oos = Column(JSON)
        walk_forward_results = Column(JSON)
        monte_carlo_results = Column(JSON)
        bias_check_results = Column(JSON)
        report_path = Column(String)
        mql5_file_path = Column(String)

except ImportError:
    # SQLAlchemy not installed — models not available, using InMemorySessionStore
    class StrategySession:  # type: ignore
        pass
