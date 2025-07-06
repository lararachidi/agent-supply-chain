# Databricks notebook source
# MAGIC %md
# MAGIC This project is based on Databricks' supply chain optimization solution accelerator available at: https://github.com/databricks-industry-solutions/supply-chain-optimization. For more information about this solution accelerator, visit https://www.databricks.com/solutions/accelerators/supply-chain-distribution-optimization.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Supply Chain Data Analysis
# MAGIC
# MAGIC This notebook performs:
# MAGIC
# MAGIC - Raw Material Analysis: Identifies critical materials with supply shortages by comparing demand vs supply data
# MAGIC - BOM Relationship Mapping: Analyzes the hierarchical relationships between raw materials, intermediate materials and final products
# MAGIC - Custom Functions:
# MAGIC   - product_from_raw: Maps a raw material to all downstream products
# MAGIC   - raw_from_product: Maps a product to all upstream raw materials
# MAGIC   - revenue_risk: Calculates potential revenue impact from raw material shortages

# COMMAND ----------

# Create widgets for catalog and database names
dbutils.widgets.text("catalog_name", "main", "Catalog Name")
dbutils.widgets.text("db_name", "supply_chain_db", "Database Name")

# COMMAND ----------

# Get values from widgets
catalog_name = dbutils.widgets.get("catalog_name")
db_name = dbutils.widgets.get("db_name")


# COMMAND ----------

# MAGIC %run ./_resources/00-setup $reset_all_data=false $catalogName=$catalog_name $dbName=$db_name

# COMMAND ----------

# Use the variables from the setup script for consistency
catalogName = catalog_name
dbName = db_name

print(f"Using catalogName: {catalogName}")
print(f"Using dbName: {dbName}")

# COMMAND ----------

# MAGIC %md
# MAGIC The goal is to identify the most critical raw material with potential shortages.
# MAGIC
# MAGIC We join raw_material_demand and raw_material_supply to compute shortages for each raw material and look at the difference between total supply and total demand

# COMMAND ----------

mat_number = spark.sql(f"""
SELECT demand.RAW, SUM(demand.Demand_Raw) as total_demand, SUM(supply.supply) as total_supply, total_supply-total_demand as demand_difference
FROM {catalogName}.{dbName}.raw_material_demand demand
LEFT JOIN {catalogName}.{dbName}.raw_material_supply supply ON demand.RAW=supply.raw
WHERE supply.supply is not null
GROUP BY demand.RAW
ORDER BY demand_difference ASC
LIMIT 1
""").collect()[0][0]
print(f"Most critical raw material: {mat_number}")

# COMMAND ----------

# MAGIC %md
# MAGIC We query the bill of materials relationships. We map raw materials, intermediate materials and products. It gives us the hierarchical relationships: `raw_material → primary_material → intermediate_material → product`.
# MAGIC

# COMMAND ----------

spark.sql(f"""SELECT
    bom_primary.material_in as raw_material, bom_intermediate.qty as raw_qty, 
    bom_intermediate.material_in as primary_material, bom_intermediate.qty as primary_qty, 
    bom_intermediate.material_out as intermediate_material, bom_product.qty as intermediate_qty,
    bom_product.material_out as product 
FROM {catalogName}.{dbName}.bom bom_primary
JOIN {catalogName}.{dbName}.bom bom_intermediate ON bom_primary.material_out = bom_intermediate.material_in
JOIN {catalogName}.{dbName}.bom bom_product ON bom_intermediate.material_out = bom_product.material_in""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC We create a function `product_from_raw`. It takes a `raw_material` as input and returns all downstream relationships (raw --> product)
# MAGIC
# MAGIC We filter results by the given material. 

# COMMAND ----------

spark.sql(f'''
CREATE OR REPLACE FUNCTION {catalogName}.{dbName}.product_from_raw (
    input_material STRING COMMENT "MAT number of the raw material" DEFAULT "{mat_number}"
) RETURNS TABLE (
    raw_material STRING,
    raw_qty INT,
    primary_material STRING,
    primary_qty INT,
    intermediate_material STRING,
    intermediate_qty INT,
    product STRING
) COMMENT "Returns the raw and intermediate materials required to produce a SKU / Product"  RETURN 
SELECT
    bom_primary.material_in as raw_material, bom_intermediate.qty as raw_qty, 
    bom_intermediate.material_in as primary_material, bom_intermediate.qty as primary_qty, 
    bom_intermediate.material_out as intermediate_material, bom_product.qty as intermediate_qty,
    bom_product.material_out as product 
FROM {catalogName}.{dbName}.bom bom_primary
JOIN {catalogName}.{dbName}.bom bom_intermediate ON bom_primary.material_out = bom_intermediate.material_in
JOIN {catalogName}.{dbName}.bom bom_product ON bom_intermediate.material_out = bom_product.material_in
WHERE 
    product_from_raw.input_material = bom_primary.material_in 
    OR product_from_raw.input_material = bom_intermediate.material_in
    OR product_from_raw.input_material = bom_product.material_in
''')

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC We define a function that takes a product as input and returns all upstream relationships (product → raw).

# COMMAND ----------

product = "syringe_1"

spark.sql(f'''
CREATE OR REPLACE FUNCTION {catalogName}.{dbName}.raw_from_product (
    input_product STRING COMMENT "get the raw materials for a particular product" DEFAULT "{product}"
) RETURNS TABLE (
    raw_material STRING,
    raw_qty INT,
    primary_material STRING,
    primary_qty INT,
    intermediate_material STRING,
    intermediate_qty INT,
    product STRING
) COMMENT "Returns the raw and intermediate materials required to produce a SKU / Product"  RETURN 
SELECT
    bom_primary.material_in as raw_material, bom_intermediate.qty as raw_qty, 
    bom_intermediate.material_in as primary_material, bom_intermediate.qty as primary_qty, 
    bom_intermediate.material_out as intermediate_material, bom_product.qty as intermediate_qty,
    bom_product.material_out as product 
FROM {catalogName}.{dbName}.bom bom_primary
JOIN {catalogName}.{dbName}.bom bom_intermediate ON bom_primary.material_out = bom_intermediate.material_in
JOIN {catalogName}.{dbName}.bom bom_product ON bom_intermediate.material_out = bom_product.material_in
WHERE 
    input_product = bom_product.material_out
''')

# COMMAND ----------

spark.sql(f"SELECT * FROM {catalogName}.{dbName}.raw_from_product('syringe_1')").display()

# COMMAND ----------

spark.sql(f""" 
    SELECT * FROM {catalogName}.{dbName}.product_from_raw('{mat_number}')          
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC We create a function that calculates the risk of revenue loss due to raw material shortages.
# MAGIC
# MAGIC * material_shortage: Raw material shortage.
# MAGIC * product_shortage: Impact on product availability.
# MAGIC * revenue_risk: Potential revenue loss.
# MAGIC
# MAGIC We compute the shortages for each raw material. We map raw materials to products. We then join with prices to calculate revenues loss based on product prices. 

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {catalogName}.{dbName}.revenue_risk (
  raw_material STRING COMMENT "MAT number of the raw material, for example revenue_risk.raw_material" DEFAULT "{mat_number}"
) RETURNS TABLE (
  material STRING,
  product STRING,
  material_supply INT,
  material_demand INT,
  material_shortage INT,
  product_shortage FLOAT,
  revenue_risk DECIMAL(10,2)
) COMMENT "Returns the forecasted revenue risk due to shortages given a raw material" RETURN 

WITH material_shortage AS (
    SELECT demand.RAW as material, SUM(demand.Demand_Raw) as total_demand, SUM(supply.supply) as total_supply, 
        CASE WHEN SUM(demand.Demand_Raw) > SUM(supply.supply) THEN SUM(demand.Demand_Raw)-SUM(supply.supply) ELSE 0 END as shortage
    FROM {catalogName}.{dbName}.raw_material_demand demand
    LEFT JOIN {catalogName}.{dbName}.raw_material_supply supply ON demand.RAW=supply.raw
    GROUP BY demand.RAW
)

SELECT 
    material_shortage.material, 
    pfr.product,
    material_shortage.total_supply as material_supply,
    material_shortage.total_demand as material_demand,
    material_shortage.shortage as material_shortage,
    material_shortage.shortage / SUM(pfr.intermediate_qty) / SUM(pfr.primary_qty / pfr.raw_qty) as product_shortage,
    (material_shortage.shortage / SUM(pfr.intermediate_qty) / SUM(pfr.primary_qty / pfr.raw_qty)) * SUM(list_prices.price) as revenue_at_risk
FROM material_shortage
JOIN (
    SELECT *
    FROM {catalogName}.{dbName}.product_from_raw(revenue_risk.raw_material)
) pfr ON material_shortage.material=pfr.raw_material
JOIN (
    SELECT price, product
    FROM {catalogName}.{dbName}.list_prices
) list_prices ON lower(list_prices.product) = lower(pfr.product)
WHERE material_shortage.material = revenue_risk.raw_material
GROUP BY material_shortage.material, pfr.product, material_shortage.total_supply, material_shortage.total_demand, material_shortage.shortage
;
""")

# COMMAND ----------

spark.sql(f"""
SELECT product, revenue_risk
FROM {catalogName}.{dbName}.revenue_risk('{mat_number}')
""").display()


# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2023 Databricks, Inc. All rights reserved. The source in this notebook is provided subject to the Databricks License [https://databricks.com/db-license-source].  All included or referenced third party libraries are subject to the licenses set forth below.
# MAGIC
# MAGIC | library                                | description             | license    | source                                              |
# MAGIC |----------------------------------------|-------------------------|------------|-----------------------------------------------------|
# MAGIC | pulp                                 | A python Linear Programming API      | https://github.com/coin-or/pulp/blob/master/LICENSE        | https://github.com/coin-or/pulp                      |