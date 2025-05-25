# Databricks notebook source
# MAGIC %md Credits: This is adapted from a solution accelerator for supply chain optimization, available at https://github.com/databricks-industry-solutions/supply-chain-optimization. For more information about this solution accelerator, visit https://www.databricks.com/solutions/accelerators/supply-chain-distribution-optimization. 

# COMMAND ----------

# MAGIC %md
# MAGIC # Introduction
# MAGIC
# MAGIC
# MAGIC **Context**:
# MAGIC We have a pharmaceutical supply chain, with 3 plants that deliver a set of 30 product SKUs to 5 distribution centers. Each distribution center is assigned to a set of between 30 and 60 wholesalers. All these parameters are treated as variables such that the pattern of the code may be scaled. Each wholesaler has a demand series for each of the products. 
# MAGIC
# MAGIC
# MAGIC **The following are given**:
# MAGIC - the demand series for each product in each wholesaler
# MAGIC - a mapping table that uniquely assigns each distribution center to a wholesaler. This is a simplification as it is possible that one wholesaler obtains products from different distribution centers.
# MAGIC - a table that assigns the costs of shipping a product from each manufacturing plant to each distribution center
# MAGIC - a table of the maximum quantities of product that can be produced and shipped from each plant to each of the distribution centers
# MAGIC
# MAGIC
# MAGIC **We proceed in 2 steps**:
# MAGIC - *Demand Forecasting*: The demand forecast is first estimated one week ahead. Aggregation yields the demand for each distribution center: 
# MAGIC   - For the demand series for each product within each wholesaler we generate a one-week-ahead forecast
# MAGIC   - For the distribution center, we derive next week's estimated demand for each product
# MAGIC - *Minimization of transportation costs*: From the cost and constraints tables of producing by and shipping from a plant to a distribution center we derive cost-optimal transportation.
# MAGIC
# MAGIC <img src="https://raw.githubusercontent.com/databricks-industry-solutions/supply-chain-optimization/main/pictures/Plant_DistributionCenter_Store_Prouct_2.png" width=70%>

# COMMAND ----------

# MAGIC %md
# MAGIC # Setup
# MAGIC Run 01-data-generator

# COMMAND ----------

# MAGIC %md
# MAGIC ## Set up catalog and database name
# MAGIC
# MAGIC The catalog and database will be created automatically if they do not exist. The data generator script will create the necessary tables and populate them with sample data.

# COMMAND ----------

# Note: dbutils is automatically available in Databricks notebooks
# Create widgets for catalog and database names
dbutils.widgets.text("catalog_name", "supply_chain", "Catalog Name")
dbutils.widgets.text("db_name", "supply_chain_db", "Database Name")

# Get values from widgets
catalog_name = dbutils.widgets.get("catalog_name")
db_name = dbutils.widgets.get("db_name")

# Display the values being used
print(f"Using catalog: {catalog_name}")
print(f"Using database: {db_name}")

# COMMAND ----------
# Create catalog and schema
spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog_name}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {db_name}")

# COMMAND ----------
# MAGIC %run ./_resources/00-setup $reset_all_data=true $catalogName=$catalog_name $dbName=$db_name