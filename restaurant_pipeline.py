import logging
import pandas as pd
import csv
import pyarrow
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

#logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
#Extract
def extract_csv(filename):
    data = pd.read_csv(filename)
    logger.info("Customers count: %s", len(data))
    return data
def extract_json(filename):
    data = pd.read_json(filename)
    logger.info("Restaurants count: %s", len(data))
    return data
def extract_parquet(filename):
    data = pd.read_parquet(filename)
    logger.info("Orders count: %s", len(data))
    return data
#Reject records with:
#missing IDs;
#invalid dates;
#zero or negative quantities;
#zero or negative prices;
#invalid order statuses.

#Transform
def transform_customers(df):
    df = df.drop_duplicates(subset="customer_id")
    df = df.replace("", pd.NA)
    df["customer_name"] = df["customer_name"].str.strip().str.title()
    df["email"] = df["email"].str.strip().str.title()
    df["city"] = df["city"].str.strip().str.title()
    df["signup_date"] = pd.to_datetime(df["signup_date"], errors = "coerce", format = "mixed")
    logger.info("Transformed customers count: %s", len(df))
    return df

def transform_restaurants(df):
    df = df.drop_duplicates(subset="restaurant_id")
    logger.info("Transformed restaurants count: %s", len(df))
    return df

def transform_orders(df):
    df = df.drop_duplicates(subset="order_id")
    df["order_date"] = pd.to_datetime(df['order_date'], errors = 'coerce', format = 'mixed')
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["total_amount"] = df["quantity"] * df["unit_price"]
    logger.info("Transformed orders count: %s", len(df))
    return df

def validate_customer(df):
    invalid = (
        df["signup_date"].isna() | df["customer_id"].isna() | df["customer_name"].isna() | df["email"].isna() | df["city"].isna()
        )
    errors_df = df[invalid].copy()
    def get_error_reason(row):
        reasons = []
        if pd.isna(row["customer_id"]):
            reasons.append("Missing customer id")
        if pd.isna(row['customer_name']):
            reasons.append("Missing customer name")
        if pd.isna(row['email']):
            reasons.append("Missing email")
        if pd.isna(row['city']):
            reasons.append("Missing city")
        if pd.isna(row['signup_date']):
            reasons.append("Missing signup date")
        return ", ".join(reasons)
    errors_df['error_reason'] = errors_df.apply(get_error_reason, axis=1)
    valid_df = df[~invalid].copy()
    logger.info("%s Valid customer rows and %s rejected customer rows", len(valid_df), len(errors_df))
    return errors_df, valid_df

def validate_restaurant(df):
    invalid = (
        df["restaurant_id"].isna() | df["restaurant_name"].isna() | df["city"].isna() | df["category"].isna()
        )
    errors_df = df[invalid].copy()
    def get_error_reason(row):
        reasons = []
        if pd.isna(row["restaurant_id"]):
            reasons.append("Missing restaurant id")
        if pd.isna(row['restaurant_name']):
            reasons.append("Missing restaurant name")
        if pd.isna(row['city']):
            reasons.append("Missing city")
        if pd.isna(row['category']):
            reasons.append("Missing category")
        return ", ".join(reasons)
    errors_df['error_reason'] = errors_df.apply(get_error_reason, axis=1)
    valid_df = df[~invalid].copy()
    logger.info("%s Valid restaurant rows and %s rejected restaurant rows", len(valid_df), len(errors_df))
    return errors_df, valid_df

def validate_order(df, valid_customer, valid_restaurant):
    invalid = (
        ~df["customer_id"].isin(valid_customer["customer_id"]) | ~df["restaurant_id"].isin(valid_restaurant["restaurant_id"]) |df["customer_id"].isna() | df["restaurant_id"].isna() | df["quantity"].isna() | df["unit_price"].isna() | (df["quantity"]<=0) | (df["unit_price"]<=0) | df["order_date"].isna()
        )
    errors_df = df[invalid].copy()
    def get_error_reason(row):
        reasons = []
        if pd.isna(row['customer_id']):
            reasons.append("Missing customer id")
        if row["customer_id"] not in valid_customer["customer_id"].values:
            reasons.append("Customer id does not exist")
        if pd.isna(row['restaurant_id']):
            reasons.append("Missing restaurant id")
        if row["restaurant_id"] not in valid_restaurant["restaurant_id"].values:
            reasons.append("Restaurant id does not exist")
        if pd.isna(row['quantity']):
            reasons.append("Missing quantity")
        if pd.isna(row['unit_price']):
            reasons.append("Missing unit price")
        if (row['quantity']<=0):
            reasons.append("Quantity less than 0")
        if (row['unit_price']<=0):
            reasons.append("Unit_price less than 0")
        if pd.isna(row['order_date']):
            reasons.append("Missing order date")
        return ", ".join(reasons)
    errors_df['error_reason'] = errors_df.apply(get_error_reason, axis=1)
    valid_df = df[~invalid].copy()
    logger.info("%s Valid order rows and %s rejected order rows", len(valid_df), len(errors_df))
    return errors_df, valid_df

def save_errors(errors, filename):
    os.makedirs('errors', exist_ok=True)
    errors.to_csv(f'errors/{filename}', index=False)
    logger.info("Saved %s errors to errors/%s", len(errors), filename)

#Load
def load_to_postgres(df, df1, df2):
    load_dotenv(override=True)
    try:
        logging.info("Connecting to PostgreSQL")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST")
        db_name = os.getenv("DB_NAME")
        db_port = os.getenv("DB_PORT", "5432")

        print("USER:", db_user)
        print("HOST:", db_host)
        print("DATABASE:", db_name)

        engine = create_engine(
            f"postgresql+psycopg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        )
        df.to_sql("customer", engine, if_exists="replace", index=False)
        df1.to_sql("restaurant", engine, if_exists="replace", index=False)
        df2.to_sql("orders", engine, if_exists="replace", index=False)
        logging.info("Loaded %s customers into PostgreSQL.", len(df))
        logging.info("Loaded %s restaurants into PostgreSQL.", len(df1))
        logging.info("Loaded %s orders into PostgreSQL.", len(df2))
    except Exception:
        logging.exception("Failed to connect to PostgreSQL.")
        raise

#Run pipeline
def run_pipeline():
    logger.info("=" * 40)
    logger.info("Pipeline started")
    
    raw_customers = extract_csv("customers.csv")
    raw_restaurants = extract_json("restaurants.json")
    raw_orders = extract_parquet("orders.parquet")
    customer = transform_customers(pd.DataFrame(raw_customers))
    restaurant = transform_restaurants(pd.DataFrame(raw_restaurants))
    order = transform_orders(pd.DataFrame(raw_orders))
    customer_error, valid_customer = validate_customer(customer)
    restaurant_error, valid_restaurant = validate_restaurant(restaurant)
    order_error, valid_order = validate_order(order, valid_customer, valid_restaurant)
    save_errors(customer_error, "customer_error.csv")
    save_errors(restaurant_error, "restaurant_error.csv")
    save_errors(order_error, "order_error.csv")
    load_to_postgres(valid_customer, valid_restaurant, valid_order)
    
    logger.info("Pipeline completed successfully")
    logger.info("=" * 40)

if __name__ == '__main__':
    run_pipeline()