# 🍽️ Restaurant Chain Orders Pipeline

An ETL pipeline that reads restaurant data from three different file formats, cleans and validates it, separates rejected records with a reason for rejection, and loads the clean data into PostgreSQL. It ships with SQL business reports, pytest tests, structured logging, and a Docker setup.

## Overview

| Source | Format | Contents |
|---|---|---|
| `customers.csv` | CSV | customer details |
| `restaurants.json` | JSON | restaurant details |
| `orders.parquet` | Parquet | order transactions |

```
Extract  →  Transform  →  Validate  →  Save rejects  →  Load to PostgreSQL
(3 formats)  (clean)     (rules)      (errors/*.csv)    (3 tables)
```

## Features

- **Multi-format extraction**: CSV, JSON and Parquet read into Pandas DataFrames.
- **Data cleaning**: duplicate removal, whitespace and casing fixes, type conversion, date parsing with `errors="coerce"`.
- **Validation with reasons**: every rejected row gets an `error_reason` explaining exactly why it failed.
- **Referential checks**: orders pointing to a customer or restaurant that does not exist are rejected.
- **Error separation**: rejected records are written to an `errors/` folder, never silently dropped.
- **Logging**: timestamps and row counts for every stage, written to both the terminal and `pipeline.log`.
- **Secure configuration**: database credentials come from environment variables (`.env`), never hard-coded.
- **Tested**: pytest suite covering cleaning and validation logic.
- **Containerised**: runs the same way on any machine with Docker.

## Project Structure

```
restaurant_pipeline/
├── restaurant_pipeline.py   # main pipeline (extract, transform, validate, load)
├── test_pipeline.py         # pytest tests
├── customers.csv            # source data
├── restaurants.json         # source data
├── orders.parquet           # source data
├── requirements.txt         # Python dependencies
├── Dockerfile               # container definition
├── .dockerignore            # files excluded from the Docker image
├── .gitignore               # files excluded from Git
├── .env                     # database credentials (not committed)
├── errors/                  # rejected records (auto-created)
│   ├── customer_error.csv
│   ├── restaurant_error.csv
│   └── order_error.csv
└── pipeline.log             # run log (auto-generated)
```

## Pipeline Stages

### 1. Extract
Each source is read with the reader suited to its format and the row count is logged.

### 2. Transform

| Dataset | Cleaning applied |
|---|---|
| Customers | remove duplicate `customer_id`, trim whitespace, title-case name and city, normalise email, parse `signup_date` |
| Restaurants | remove duplicate `restaurant_id` |
| Orders | remove duplicate `order_id`, parse `order_date`, convert `quantity` and `unit_price` to numeric, calculate `total_amount = quantity * unit_price` |

### 3. Validate

A record is rejected if it breaks any of these rules:

| Dataset | Rejection rules |
|---|---|
| Customers | missing ID, name, email, city or signup date |
| Restaurants | missing ID, name, city or category |
| Orders | missing `customer_id` or `restaurant_id`; customer or restaurant does not exist; missing or invalid date; missing, zero or negative quantity; missing, zero or negative unit price |

Each rejected row is saved with a human-readable reason, for example:

```
Quantity less than 0, Missing order date
```

### 4. Load
Valid records are written to PostgreSQL in three tables: `customer`, `restaurant`, `orders`.

## Setup (without Docker)

**1. Create and activate a virtual environment**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Create a `.env` file**
```
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=restaurant_db
```

**4. Create the database** (once, in `psql` or pgAdmin)
```sql
CREATE DATABASE restaurant_db;
```

**5. Run the pipeline**
```bash
python restaurant_pipeline.py
```

## Running with Docker

### Build the image
```bash
docker build -t restaurant-pipeline .
```

### Run the pipeline
If PostgreSQL is running on your own machine (not in a container), the container cannot reach it through `localhost`, because inside a container `localhost` means the container itself. Use `host.docker.internal` instead:

```bash
docker run --rm \
  --env-file .env \
  -e DB_HOST=host.docker.internal \
  -v "$(pwd)/errors:/app/errors" \
  restaurant-pipeline
```

| Flag | Purpose |
|---|---|
| `--rm` | remove the container when it finishes |
| `--env-file .env` | pass database credentials in at runtime (they are never baked into the image) |
| `-e DB_HOST=host.docker.internal` | overrides `localhost` so the container can reach PostgreSQL on your machine |
| `-v "$(pwd)/errors:/app/errors"` | saves rejected-record files to your machine so they survive after the container exits |

### Run the tests inside the container
```bash
docker run --rm restaurant-pipeline pytest -v
```

### If PostgreSQL also runs in Docker
Put both containers on the same network and use the database container's alias as the host:

```bash
docker network create pipeline-net

docker run -d --network pipeline-net --network-alias postgres \
  -e POSTGRES_PASSWORD=secret -e POSTGRES_DB=restaurant_db \
  -v pipeline-pgdata:/var/lib/postgresql/data \
  postgres:16

docker run --rm --network pipeline-net \
  --env-file .env -e DB_HOST=postgres \
  restaurant-pipeline
```

> **Security note:** `.env` is listed in both `.gitignore` and `.dockerignore`. Never commit it or copy it into an image.

## Running the Tests

```bash
pytest -v
```

The tests use small in-memory DataFrames (fixtures), so they never depend on real files or a database. They cover:

- duplicate removal
- rejection of invalid quantities
- rejection of invalid dates
- correct `total_amount` calculation
- presence of `error_reason` on rejected records

## SQL Reports

Run these in `psql` or pgAdmin after the pipeline has loaded the data.

```sql
-- Total items and revenue per order_status
SELECT COUNT(*) AS total_orders, SUM(quantity) AS total_items, 
SUM(total_amount) AS Total_Revenue, order_status 
FROM orders GROUP BY order_status;

-- Daily revenue
SELECT order_date, SUM(total_amount) AS daily_revenue
FROM orders
GROUP BY order_date
ORDER BY order_date;

-- Top 5 restaurants by revenue
SELECT o.restaurant_id, r.restaurant_name, SUM(o.total_amount) AS revenue
FROM orders o
INNER JOIN restaurant r ON o.restaurant_id = r.restaurant_id
GROUP BY o.restaurant_id, r.restaurant_name
ORDER BY revenue DESC
LIMIT 5;

-- Restaurant with the most items sold
SELECT o.restaurant_id, r.restaurant_name, SUM(o.quantity) AS items_sold
FROM orders o
INNER JOIN restaurant r ON o.restaurant_id = r.restaurant_id
GROUP BY o.restaurant_id, r.restaurant_name
ORDER BY items_sold DESC
LIMIT 1;

-- Highest-spending customer
SELECT o.customer_id, c.customer_name, SUM(o.total_amount) AS revenue
FROM orders o
INNER JOIN customer c ON o.customer_id = c.customer_id
GROUP BY o.customer_id, c.customer_name
ORDER BY revenue DESC
LIMIT 1;
```

## Tech Stack

- **Python 3** with **Pandas** for transformation
- **PyArrow** for Parquet support
- **SQLAlchemy** + **psycopg** for PostgreSQL loading
- **python-dotenv** for configuration
- **pytest** for testing
- **PostgreSQL** as the destination warehouse
- **Docker** for containerisation

## Author

Built as part of my data engineering learning path: Python, Pandas, SQL, PostgreSQL, logging, pytest and Docker.
