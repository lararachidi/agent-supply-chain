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
# MAGIC Run this notebook to generate the data and run all subsequent notebooks.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Set up catalog and database name
# MAGIC
# MAGIC The catalog and database will be created automatically if they do not exist. The data generator script will create the necessary tables and populate them with sample data.
# MAGIC
# MAGIC The default catalog is 'main' and schema/database is 'supply_chain_db'. Feel free to change to another catalog and schema/database.

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

# MAGIC %md
# MAGIC ## Set up OpenAI API Key Secret
# MAGIC
# MAGIC Here's the [documentation](https://docs.databricks.com/aws/en/security/secrets/?language=Databricks%C2%A0SDK%C2%A0for%C2%A0Python) to learn more about Databricks secrets and how to manage them.

# COMMAND ----------

# OpenAI‑secret bootstrap                                         

from databricks.sdk import WorkspaceClient, errors

w = WorkspaceClient()

scope_name = "openai_secret_scope"
key_name   = "openai_secret_key"
secret_val = "<add your secret here>"          # paste once, then leave blank

# Create the scope once
if scope_name not in {s.name for s in w.secrets.list_scopes()}:
    w.secrets.create_scope(scope=scope_name)
    print(f"Created secret scope `{scope_name}`")

# Write the secret only if it doesn’t already exist
try:
    _ = w.secrets.get_secret(scope=scope_name, key=key_name)
    print(f"Secret `{scope_name}/{key_name}` already exists — leaving it untouched.")
except errors.ResourceDoesNotExist:
    if not secret_val.strip():
        raise ValueError(
            f"Secret `{scope_name}/{key_name}` is missing and `secret_val` is empty. "
            "Paste your OpenAI key in `secret_val` (or via a widget) the first time."
        )
    w.secrets.put_secret(scope=scope_name, key=key_name, string_value=secret_val.strip())
    print(f"Stored new secret `{scope_name}/{key_name}`")



# COMMAND ----------

# MAGIC %run ./_resources/00-setup $reset_all_data=true 

# COMMAND ----------

# MAGIC %md
# MAGIC # Next steps
# MAGIC
# MAGIC You have two options to run the subsequent notebooks: 
# MAGIC - Option 1: Run all subsequent notebooks at once below by using a magic command.
# MAGIC - Option 2: Run each subsequent notebook manually in numerical order to follow the end-to-end process (for the next step, run notebook 02_Fine_Grained_Demand_Forecasting).

# COMMAND ----------

# MAGIC %md
# MAGIC # Option 1: Run all notebooks at once 
# MAGIC
# MAGIC You can run all the notebooks below with a magic command. 

# COMMAND ----------

# MAGIC %run ./02_Fine_Grained_Demand_Forecasting 

# COMMAND ----------

# MAGIC %run ./03_Derive_Raw_Material_Demand 

# COMMAND ----------

# MAGIC %run ./04_Optimize_Transportation 

# COMMAND ----------

# MAGIC %run ./05_Data_Analysis_&_Functions 

# COMMAND ----------

# MAGIC %run ./06_Vector_Search 

# COMMAND ----------

# MAGIC %md
# MAGIC # Warning
# MAGIC Note that the vector search index will take a few minutes to get up and running. 
# MAGIC

# COMMAND ----------

# MAGIC %run ./07_More_Functions