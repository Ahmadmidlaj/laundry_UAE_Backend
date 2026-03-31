import enum
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum, Table, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    CUSTOMER = "CUSTOMER"
    EMPLOYEE = "EMPLOYEE"

class OrderStatus(str, enum.Enum):
    NEW_ORDER = "NEW_ORDER"
    PICKED_UP = "PICKED_UP"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    mobile = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.CUSTOMER)
    
    # Address details for customers
    flat_number = Column(String)
    building_name = Column(String)
    
    orders = relationship("Order", back_populates="customer")

class LaundryItem(Base):
    __tablename__ = "laundry_items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    base_price = Column(Float, nullable=False)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"))
    status = Column(Enum(OrderStatus), default=OrderStatus.NEW_ORDER)
    
    # Scheduling
    pickup_date = Column(DateTime)
    pickup_time = Column(String)
    notes = Column(String)

    expected_delivery_date = Column(DateTime, nullable=True)
    expected_delivery_time = Column(String, nullable=True)
    
    # Financials
    estimated_price = Column(Float, default=0.0)
    final_price = Column(Float, default=0.0)
    discount_applied = Column(Float, default=0.0)
    
    # Relationships
    customer = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")
    payment = relationship("Transaction", back_populates="order", uselist=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    item_id = Column(Integer, ForeignKey("laundry_items.id"))
    
    estimated_quantity = Column(Integer, default=0)
    final_quantity = Column(Integer, default=0)
    unit_price = Column(Float) # Captured at time of order

    order = relationship("Order", back_populates="items")
    item = relationship("LaundryItem")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    received_amount = Column(Float)
    payment_method = Column(String) # Cash or Card
    delivery_date = Column(DateTime, default=func.now())
    
    order = relationship("Order", back_populates="payment")

class Offer(Base):
    __tablename__ = "offers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    min_order_amount = Column(Float, default=0.0)
    discount_amount = Column(Float, default=0.0)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)