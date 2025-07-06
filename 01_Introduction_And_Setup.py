# Databricks notebook source
# MAGIC %md Credits: This is adapted from a Databricks solution accelerator for supply chain optimization, available at https://github.com/databricks-industry-solutions/supply-chain-optimization. For more information about this solution accelerator, visit https://www.databricks.com/solutions/accelerators/supply-chain-distribution-optimization. 

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

# Create widgets for catalog and database names
dbutils.widgets.text("catalog_name", "main", "Catalog Name")
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

# MAGIC %run ./_resources/00-setup $reset_all_data=true $catalog_name=main $db_name=supply_chain_db

# COMMAND ----------

# MAGIC %md
# MAGIC # Next steps
# MAGIC
# MAGIC You have two options to run the subsequent notebooks: 
# MAGIC - Option 1: Run each subsequent notebook in numerical order to follow the end-to-end process
# MAGIC - Option 2: Run all subsequent notebooks at once below by using a magic command.

# COMMAND ----------

# MAGIC %md
# MAGIC # Optional
# MAGIC
# MAGIC You can run all the notebooks below with a magic command. 

# COMMAND ----------

# MAGIC %run ./02_Fine_Grained_Demand_Forecasting $catalog_name=main $db_name=supply_chain_db

# COMMAND ----------

# MAGIC %run ./03_Derive_Raw_Material_Demand $catalog_name=main $db_name=supply_chain_db

# COMMAND ----------

# MAGIC %run ./04_Optimize_Transportation $catalog_name=main $db_name=supply_chain_db

# COMMAND ----------

# MAGIC %run ./05_Data_Analysis_&_Functions $catalog_name=main $db_name=supply_chain_db

# COMMAND ----------

# MAGIC %run ./06_Vector_Search $catalog_name=main $db_name=supply_chain_db

# COMMAND ----------

# MAGIC %md
# MAGIC # Warning
# MAGIC Note that the vector search index will take a few minutes to get up and running. 
# MAGIC

# COMMAND ----------

# MAGIC %run ./07_More_Functions $catalog_name=main $db_name=supply_chain_db