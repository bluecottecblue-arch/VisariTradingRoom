"""
ORM Models — solo caricati se SQLAlchemy è disponibile
"""
try:
    from sqlalchemy import Boolean, Column, String, Float, Integer, Text, DateTime, JSON
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


    class Project(Base):
        __tablename__ = "projects"

        id = Column(String, primary_key=True)
        owner_username = Column(String, index=True, nullable=False)
        title = Column(String, nullable=False)
        mode = Column(String, default="strategy")
        status = Column(String, default="active")
        active_session_id = Column(String)
        latest_verdict = Column(String)
        metadata_json = Column(JSON, default={})
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


    class ProjectVersion(Base):
        __tablename__ = "project_versions"

        id = Column(String, primary_key=True)
        project_id = Column(String, index=True, nullable=False)
        session_id = Column(String, index=True)
        version_kind = Column(String, nullable=False)
        status = Column(String, default="draft")
        summary = Column(JSON, default={})
        payload = Column(JSON, default={})
        fingerprint = Column(String, index=True)
        created_at = Column(DateTime(timezone=True), server_default=func.now())


    class ProjectArtifact(Base):
        __tablename__ = "project_artifacts"

        id = Column(String, primary_key=True)
        project_id = Column(String, index=True, nullable=False)
        session_id = Column(String, index=True)
        artifact_type = Column(String, nullable=False)
        label = Column(String, nullable=False)
        storage_path = Column(String)
        metadata_json = Column(JSON, default={})
        created_at = Column(DateTime(timezone=True), server_default=func.now())


    class JobRun(Base):
        __tablename__ = "job_runs"

        id = Column(String, primary_key=True)
        project_id = Column(String, index=True)
        session_id = Column(String, index=True)
        job_type = Column(String, nullable=False)
        status = Column(String, default="queued")
        error = Column(Text)
        payload = Column(JSON, default={})
        result_summary = Column(JSON, default={})
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


    class User(Base):
        __tablename__ = "users"

        username = Column(String, primary_key=True)
        password_hash = Column(String, nullable=False)
        password_salt = Column(String, nullable=False)
        status = Column(String, default="active")
        plan = Column(String, default="standard")
        expires_at = Column(DateTime(timezone=True))
        notes = Column(Text)
        ai_provider = Column(String, default="anthropic")
        claude_api_key = Column(String)
        openai_api_key = Column(String)
        google_api_key = Column(String)
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
        last_login_at = Column(DateTime(timezone=True))


    class AcademyProfile(Base):
        __tablename__ = "academy_profiles"

        username = Column(String, primary_key=True)
        level_input = Column(String)
        detected_level = Column(String, default="beginner")
        freeform_background = Column(Text)
        recommended_module_id = Column(String)
        recommendation_reason = Column(Text)
        last_viewed_module_id = Column(String)
        last_viewed_lesson_id = Column(String)
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


    class AcademyLessonProgress(Base):
        __tablename__ = "academy_lesson_progress"

        id = Column(String, primary_key=True)
        username = Column(String, index=True, nullable=False)
        module_id = Column(String, index=True, nullable=False)
        lesson_id = Column(String, index=True, nullable=False)
        completed = Column(Boolean, default=False)
        completed_at = Column(DateTime(timezone=True))
        last_viewed_at = Column(DateTime(timezone=True))
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


    class Team(Base):
        __tablename__ = "teams"

        id = Column(String, primary_key=True)
        owner_username = Column(String, index=True, nullable=False)
        name = Column(String, nullable=False)
        slug = Column(String, index=True, nullable=False)
        brand_name = Column(String)
        primary_accent = Column(String, default="cyan")
        support_email = Column(String)
        legal_label = Column(String)
        white_label_enabled = Column(Boolean, default=False)
        settings_json = Column(JSON, default={})
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


    class TeamMember(Base):
        __tablename__ = "team_members"

        id = Column(String, primary_key=True)
        team_id = Column(String, index=True, nullable=False)
        username = Column(String, index=True, nullable=False)
        role = Column(String, default="viewer")
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


    class ResearchDataset(Base):
        __tablename__ = "research_datasets"

        id = Column(String, primary_key=True)
        owner_username = Column(String, index=True, nullable=False)
        project_id = Column(String, index=True)
        title = Column(String, nullable=False)
        source = Column(String, nullable=False)
        symbol = Column(String)
        timeframe = Column(String)
        date_from = Column(String)
        date_to = Column(String)
        row_count = Column(Integer, default=0)
        quality_json = Column(JSON, default={})
        metadata_json = Column(JSON, default={})
        storage_path = Column(String)
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


    class ResearchModelRun(Base):
        __tablename__ = "research_model_runs"

        id = Column(String, primary_key=True)
        dataset_id = Column(String, index=True, nullable=False)
        owner_username = Column(String, index=True, nullable=False)
        project_id = Column(String, index=True)
        title = Column(String, nullable=False)
        model_type = Column(String, nullable=False)
        config_json = Column(JSON, default={})
        result_json = Column(JSON, default={})
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

except ImportError:
    # SQLAlchemy not installed — models not available, using InMemorySessionStore
    class StrategySession:  # type: ignore
        pass

    class Project:  # type: ignore
        pass

    class ProjectVersion:  # type: ignore
        pass

    class ProjectArtifact:  # type: ignore
        pass

    class JobRun:  # type: ignore
        pass

    class User:  # type: ignore
        pass

    class AcademyProfile:  # type: ignore
        pass

    class AcademyLessonProgress:  # type: ignore
        pass

    class Team:  # type: ignore
        pass

    class TeamMember:  # type: ignore
        pass

    class ResearchDataset:  # type: ignore
        pass

    class ResearchModelRun:  # type: ignore
        pass
