import sqlalchemy

engine = sqlalchemy.create_engine(
    "postgresql+psycopg2://postgres:********ITORO.2014@localhost:5432/postgres"
)


connection = engine.connect()
print("SwitchGuard Engine successfully connected to PostgreSQL!")
connection.close()
