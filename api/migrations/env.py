from alembic import context

from api.app.config import Settings
from api.app.database import Base, make_engine
from api.app.models import Lead  # noqa: F401 - register metadata

target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(
        url=Settings.from_env().database_url, target_metadata=target_metadata, literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = make_engine(Settings.from_env().database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
