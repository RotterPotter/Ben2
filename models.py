import sqlalchemy.orm as orm
from sqlalchemy import ForeignKey, DateTime, Integer, String, JSON, Boolean
from datetime import datetime
from database import Base

class Barber(Base):
    __tablename__ = 'barbers'

    id = orm.mapped_column(Integer, primary_key=True)
    name = orm.mapped_column(String)

    appointments = orm.relationship(
        "Appointment",
        back_populates="barber",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

class Appointment(Base):
    __tablename__ = 'appointments'

    id = orm.mapped_column(Integer, primary_key=True, autoincrement=True)
    barber_id = orm.mapped_column(Integer, ForeignKey('barbers.id', ondelete="CASCADE"))
    datetime = orm.mapped_column(DateTime)
    client_name = orm.mapped_column(String)
    phone_number = orm.mapped_column(String)

    barber = orm.relationship("Barber", back_populates="appointments")

    def to_dict(self):
        return {
            "id": self.id,
            "barber_name": self.barber.name,
            "datetime": self.datetime.isoformat(),
            "client_name": self.client_name,
            "phone_number": self.phone_number
        }

class Message(Base):
    __tablename__ = 'messages'

    id = orm.mapped_column(Integer, primary_key=True, autoincrement=True)
    name = orm.mapped_column(String)
    email = orm.mapped_column(String)
    message = orm.mapped_column(String)

class DialogSession(Base):
    __tablename__ = 'sessions'
    id = orm.mapped_column(String, primary_key=True)
    conversation_history = orm.relationship("DialogMessages", back_populates="session", cascade="all, delete-orphan")

class DialogMessages(Base):
    __tablename__ = 'dialog_messages'
    id = orm.mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id = orm.mapped_column(String, ForeignKey('sessions.id', ondelete="CASCADE"))
    user_message = orm.mapped_column(String)
    bot_message = orm.mapped_column(String)
    timestamp = orm.mapped_column(DateTime, default=datetime.now)

    session = orm.relationship("DialogSession", back_populates="conversation_history")

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_message": self.user_message,
            "bot_message": self.bot_message,
            "timestamp": self.timestamp.isoformat()  # Convert datetime to ISO format
        }

class PhoneNumber(Base):
    __tablename__= 'phone_numbers'
    id = orm.mapped_column(Integer, primary_key=True, autoincrement=True)
    number = orm.mapped_column(String)
    client_name = orm.mapped_column(String)
    confirmed = orm.mapped_column(Boolean, default=False)
    timestamp = orm.mapped_column(DateTime, default=datetime.now)