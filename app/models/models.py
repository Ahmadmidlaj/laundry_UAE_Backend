import enum
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum, Table, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
import string
import random

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


def generate_referral_code():
    """Helper to generate a random 8-char code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

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

    # referral_code = Column(String, unique=True, index=True, nullable=True)
    referral_code = Column(String, unique=True, index=True, default=generate_referral_code)
    referred_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    wallet_balance = Column(Float, default=0.0)
    
    orders = relationship("Order", back_populates="customer")

    referrals = relationship("User", backref="referred_by", remote_side=[id])

class LaundryItem(Base):
    __tablename__ = "laundry_items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    # base_price = Column(Float, nullable=False)

    services = relationship("ItemServicePrice", back_populates="item", cascade="all, delete-orphan")

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

    credits_used = Column(Float, default=0.0)

    hanger_needed = Column(Boolean, default=False)
    
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

    service_category_id = Column(Integer, ForeignKey("service_categories.id"), nullable=False)
    
    estimated_quantity = Column(Integer, default=0)
    final_quantity = Column(Integer, default=0)
    unit_price = Column(Float) # Captured at time of order

    order = relationship("Order", back_populates="items")
    item = relationship("LaundryItem")

    service_category = relationship("ServiceCategory")

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
    discount_type = Column(String, default="FIXED")

class Building(Base):
    __tablename__ = "buildings"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    # Storing flats as a JSON array (e.g., ["101", "102", "A1"]) is perfectly scalable 
    # for this use-case and prevents unnecessary table joins.
    flats = Column(JSON, default=list) 
    is_active = Column(Boolean, default=True) # Soft-delete to protect historical user records



class ExpenseCategory(Base):
    __tablename__ = "expense_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("expense_categories.id"), nullable=False)
    amount = Column(Float, nullable=False)
    expense_date = Column(DateTime(timezone=True), default=func.now())
    remarks = Column(String, nullable=True)
    
    # Relationship allows us to easily fetch the category name when querying an expense
    category = relationship("ExpenseCategory")


class SystemConfig(Base):
    """Global admin configurations for the application."""
    __tablename__ = "system_configs"
    id = Column(Integer, primary_key=True, index=True)
    
    # Referral System Toggles
    referral_system_enabled = Column(Boolean, default=False)
    reward_credits_per_referral = Column(Float, default=50.0) # E.g., Give 50 credits
    credit_conversion_rate = Column(Float, default=1.0)       # E.g., 1 credit = 1 AED


class ServiceCategory(Base):
    __tablename__ = "service_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False) # e.g., "Wash & Iron", "Dry Clean"
    is_active = Column(Boolean, default=True)

class ItemServicePrice(Base):
    __tablename__ = "item_service_prices"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("laundry_items.id", ondelete="CASCADE"), nullable=False)
    service_category_id = Column(Integer, ForeignKey("service_categories.id", ondelete="CASCADE"), nullable=False)
    price = Column(Float, nullable=False)

    item = relationship("LaundryItem", back_populates="services")
    category = relationship("ServiceCategory")