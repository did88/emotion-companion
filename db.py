from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class EmotionRecord(Base):
    __tablename__ = 'emotion_history'

    id = Column(String, primary_key=True)
    email = Column(String)
    user_input = Column(Text)
    gpt_reply = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

engine = create_engine('sqlite:///emotion_history.db')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
