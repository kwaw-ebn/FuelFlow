from alembic import context
from app.main import engine, Base
config=context.config
target_metadata=Base.metadata

def run(connection):
    context.configure(connection=connection,target_metadata=target_metadata,render_as_batch=connection.dialect.name=='sqlite',compare_type=True)
    with context.begin_transaction():context.run_migrations()
if context.is_offline_mode():
    context.configure(url=str(engine.url),target_metadata=target_metadata,literal_binds=True)
    with context.begin_transaction():context.run_migrations()
elif config.attributes.get('connection') is not None:
    run(config.attributes['connection'])
else:
    with engine.connect() as connection:
        if connection.dialect.name=='postgresql':
            connection.exec_driver_sql('SELECT pg_advisory_lock(88441002)');connection.commit()
        try:run(connection)
        finally:
            if connection.dialect.name=='postgresql':connection.exec_driver_sql('SELECT pg_advisory_unlock(88441002)');connection.commit()
