from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Import models through the models package to ensure all are registered
import app.models  # noqa: F401
