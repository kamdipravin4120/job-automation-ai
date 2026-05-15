"""SQLAlchemy ORM package. Aggregate modules import the shared Base from here."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import aggregates so Base.metadata is populated when migrations or tests load this package.
from . import (  # noqa: E402, F401
    device,
    integration,
    job,
    application,
    run,
    draft,
    thread,
    selector_override,
    audit_log,
    fcm_token,
    config_version,
    saved_search,
)
