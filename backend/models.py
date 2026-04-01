from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    phone = Column(String, unique=True)
    email = Column(String, unique=True)
    password_hash = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    deliveries = relationship("Delivery", back_populates="user")
    secondary_contacts = relationship("SecondaryContact", back_populates="user")


class SecondaryContact(Base):
    __tablename__ = "secondary_contacts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    phone = Column(String)
    accepted = Column(Boolean, default=False)

    user = relationship("User", back_populates="secondary_contacts")


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    tracking_id = Column(String, unique=True)
    retailer = Column(String)
    status = Column(String, default="pending")
    # pending → eta_sent → delivered → escalating → picked_up → stolen

    eta_sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    picked_up_at = Column(DateTime, nullable=True)
    secondary_alerted_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="deliveries")
    events = relationship("DeliveryEvent", back_populates="delivery")


class DeliveryEvent(Base):
    __tablename__ = "delivery_events"

    id = Column(Integer, primary_key=True, index=True)
    delivery_id = Column(Integer, ForeignKey("deliveries.id"))
    event_type = Column(String)  # eta_sent, delivered, escalation_1, escalation_2, secondary_alerted, secondary_alert_skipped, secondary_alert_failed, picked_up
    timestamp = Column(DateTime, default=datetime.utcnow)
    note = Column(String, nullable=True)

    delivery = relationship("Delivery", back_populates="events")
