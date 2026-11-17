-- Lab 05 · The table the function creates with { "action": "init" }.
-- You can also run this yourself from the RDS Query Editor or psql.

CREATE TABLE IF NOT EXISTS products (
  id         SERIAL PRIMARY KEY,
  name       TEXT NOT NULL,
  price      NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Useful queries
SELECT * FROM products ORDER BY id DESC LIMIT 20;
SELECT count(*) AS products, sum(price) AS total_value FROM products;
