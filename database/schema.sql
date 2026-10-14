CREATE TABLE extracted_entities (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255),
    extracted_name VARCHAR(255),
    invoice_date DATE,
    total_price NUMERIC(15,2)
);