import pytest
import pandas as pd
import numpy as np
from restaurant_pipeline import (transform_orders, validate_order, validate_customer, validate_restaurant)

@pytest.fixture
def order():
    return pd.DataFrame({
        "order_id": [1, 1, 2],
        "customer_id": [1, 1, 2],
        "restaurant_id": [205, 205, 205],
        "order_date": [
            "2026-10-01",
            "2026-10-01",
            "2026-10-02"
        ],
        "quantity": [2, 2, 3],
        "unit_price": [1000, 1000, 2000],
        "payment_status": ["Paid", "Paid", "Pending"],
        "order_status": ["Completed", "Completed", "Pending"],
        "total_amount": [2000, 2000, 6000],
        "error_reason": [None, None, None]
    })
@pytest.fixture 
def customers(): 
    return pd.DataFrame({
    "customer_id": [1, 2],
    "customer_name": ["Ada", "Tunde"],
    "email": ["ada@example.com", "tunde@example.com"],
    "city": ["Port Harcourt", "Lagos"],
    "signup_date": ["2026-01-10", "2026-02-15"]
})
@pytest.fixture 
def restaurants(): 
    return pd.DataFrame({
    "restaurant_id": [205],
    "restaurant_name": ["Ocean Catch"],
    "city": ["Port Harcourt"],
    "category": ["Seafood"]
})

def test_duplicates_removed(order):
    order = transform_orders(order)
    assert order['order_id'].is_unique

def test_invalid_quantities_rejected(order, customers, restaurants):
    order.loc[0, "quantity"] = -2
    order = transform_orders(order)
    customer_error, valid_customer = validate_customer(customers)
    restaurant_error, valid_restaurant = validate_restaurant(restaurants)
    error_order, valid_order = validate_order(order, valid_customer, valid_restaurant)
    assert (valid_order["quantity"] > 0).all()
    assert len(error_order) == 1

def test_invalid_dates_rejected(order, customers, restaurants):
    order.loc[0, "order_date"] = "not-a-date"
    order = transform_orders(order)
    customer_error, valid_customer = validate_customer(customers)
    restaurant_error, valid_restaurant = validate_restaurant(restaurants)
    error_order, valid_order = validate_order(order, valid_customer, valid_restaurant)
    assert len(error_order) == 1

def test_total_amount_calculated_correctly(order):
    order = transform_orders(order)
    assert  order.loc[ order["order_id"] == 1, "total_amount"].iloc[0] == 2000

def rejected_records_contain_error_reason(order, customers, restaurants):
    order.loc[0, "quantity"] = -2
    order = transform_orders(order)
    customer_error, valid_customer = validate_customer(customers)
    restaurant_error, valid_restaurant = validate_restaurant(restaurants)
    error_order, valid_order = validate_order(order, valid_customer, valid_restaurant)
    assert "error_reason" in error_order.columns
    assert error_order["error_reason"].notna().all()