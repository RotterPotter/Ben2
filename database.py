from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import settings

# Base for models
class Base(DeclarativeBase):
    pass

db_engine = None
DBSession = None

def connect():
    global db_engine
    global DBSession

    # Engine
    db_engine = create_engine(settings.DATABASE_URL, echo=True)

    # Base.metadata.drop_all(bind=db_engine)
    # Create all tables stored in base metadata 
    Base.metadata.create_all(bind=db_engine)
    # Bind engine to the class of sessions
    DBSession = sessionmaker(bind=db_engine)

def get_db():
    global DBSession
    if DBSession is None:
        connect()
    db = DBSession()
    try:
        yield db
    finally:
        db.close()