from app import models  # noqa: F401
from app.db import Base, engine

Base.metadata.create_all(engine)
print("Database ready")
