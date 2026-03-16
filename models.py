from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base



class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    role = Column(String, default="analyst")

    failed_attempts = Column(Integer, default=0)
    lock_until = Column(DateTime, nullable=True)

    reset_token = Column(String, nullable=True)
    reset_expiry = Column(DateTime, nullable=True)

    predictions = relationship("Prediction", back_populates="user")



class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String)
    Terrorism = Column(Float)
    Banditry = Column(Float)
    Murder = Column(Float)
    Armed_Robbery = Column(Float)
    Kidnapping = Column(Float)
    Other = Column(Float)

    cluster = Column(Integer)
    risk_level = Column(String)
    recommendation = Column(String, nullable=True)  

    created_at = Column(DateTime, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="predictions")