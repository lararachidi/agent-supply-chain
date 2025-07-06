# Databricks notebook source
dbutils.widgets.dropdown("reset_all_data", "false", ["true", "false"], "Reset all data")
dbutils.widgets.text("catalog_name", "main",            "Catalog Name")   # we already set this to main
dbutils.widgets.text("db_name",      "supply_chain_db", "Database Name")  # ← new default

# COMMAND ----------

import os
import re 
import mlflow
db_prefix = "mfg_supply_chain_optimization"

# COMMAND ----------

# Get dbName and cloud_storage_path, reset and create database
current_user = dbutils.notebook.entry_point.getDbutils().notebook().getContext().tags().apply('user')
if current_user.rfind('@') > 0:
  current_user_no_at = current_user[:current_user.rfind('@')]
else:
  current_user_no_at = current_user
current_user_no_at = re.sub(r'\W+', '_', current_user_no_at)

catalogName = dbutils.widgets.get("catalog_name")
dbName = dbutils.widgets.get("db_name")
reset_all = dbutils.widgets.get("reset_all_data") == "true"

if reset_all:
    spark.sql(f"DROP DATABASE IF EXISTS {catalogName}.{dbName} CASCADE")
    spark.sql(f"""create database if not exists {catalogName}.{dbName}""")

spark.sql(f"""USE CATALOG {catalogName}""")
spark.sql(f"""USE {dbName}""")

# COMMAND ----------

dirname = os.path.dirname(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get())
filename = "01-data-generator"
if (os.path.basename(dirname) != '_resources'):
  dirname = os.path.join(dirname,'_resources')
generate_data_notebook_path = os.path.join(dirname,filename)

def generate_data():
    dbutils.notebook.run(generate_data_notebook_path, 1800, 
                         {"reset_all_data": dbutils.widgets.get("reset_all_data"), 
                          "dbName": dbName, 
                          "catalogName": catalogName})

if reset_all:
    generate_data()

# COMMAND ----------

mlflow.set_experiment('/Users/{}/supply_chain_optimization'.format(current_user))