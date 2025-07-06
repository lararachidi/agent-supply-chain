# Databricks notebook source
# MAGIC %md This project is based on Databricks' supply chain optimization solution accelerator available at: https://github.com/databricks-industry-solutions/supply-chain-optimization. For more information about this solution accelerator, visit https://www.databricks.com/solutions/accelerators/supply-chain-distribution-optimization.

# COMMAND ----------

# MAGIC %md
# MAGIC # Fine Grained Demand Forecasting

# COMMAND ----------

# MAGIC %md
# MAGIC *Prerequisite: Make sure to run 01_Introduction_And_Setup before running this notebook.*
# MAGIC
# MAGIC In this notebook we execute one-week-ahead forecast to estimate next week's demand for each wholesaler and product. We then aggregate on a distribution center level for each product.
# MAGIC
# MAGIC We're using Pandas UDFs (user-defined functions) to take your single-node data science code, and distribute it across multiple nodes

# COMMAND ----------

# Note: dbutils is automatically available in Databricks notebooks
# Create widgets for catalog and database names
dbutils.widgets.text("catalog_name", "main", "Catalog Name")
dbutils.widgets.text("db_name", "supply_chain_db", "Database Name")

# COMMAND ----------

# Get values from widgets
catalog_name = dbutils.widgets.get("catalog_name")
db_name = dbutils.widgets.get("db_name")

# Display the values being used
print(f"Using catalog: {catalog_name}")
print(f"Using database: {db_name}")

# COMMAND ----------

# MAGIC %run ./_resources/00-setup $reset_all_data=false $catalogName=$catalog_name $dbName=$db_name

# COMMAND ----------

print(catalogName)
print(dbName)

# COMMAND ----------

import os
import datetime as dt
import numpy as np
import pandas as pd

from statsmodels.tsa.api import ExponentialSmoothing

import pyspark.sql.functions as f
from pyspark.sql.types import *

# COMMAND ----------

# MAGIC %md
# MAGIC Read the already existing product demand historical table for wholesalers 

# COMMAND ----------

demand_df = spark.read.table(f"{catalogName}.{dbName}.product_demand_historical")
demand_df = demand_df.cache() # cache to optimize subsequent operations 

# COMMAND ----------

display(demand_df)

# COMMAND ----------

# #This is just to create one example for development and testing
# example_product = demand_df.select("product").orderBy("product").limit(1).collect()[0].product
# example_wholesaler = demand_df.select("wholesaler").orderBy("wholesaler").limit(1).collect()[0].wholesaler
# pdf = demand_df.filter( (f.col("product") == example_product) & (f.col("wholesaler") == example_wholesaler)  ).toPandas()
# print(pdf)

# COMMAND ----------

# MAGIC %md
# MAGIC ## One-step ahead forecast via Holt’s Winters Seasonal Method
# MAGIC Holt-Winters’ method is based on triple exponential smoothing and is able to account for both trend and seasonality.

# COMMAND ----------

def one_step_ahead_forecast(pdf: pd.DataFrame) -> pd.DataFrame:

    #Prepare time series for forecast - converts data into time series indexed by date with weekly frequency
    series_df = pd.Series(pdf['demand'].values, index=pdf['date'])
    series_df = series_df.asfreq(freq='W-MON')

    # One-step ahead forecast - fits a triple exponential smoothing model accounting for both trend and seasonality
    fit1 = ExponentialSmoothing(
        series_df,
        trend="add",
        seasonal="add",
        use_boxcox=False,
        initialization_method="estimated",
    ).fit(method="ls")
    fcast1 = fit1.forecast(1).rename("Additive trend and additive seasonal") # 1 week ahead forecast 

    # Collect Result - df containing the forecasted demand, product, wholesaler and forecast date 
    df = pd.DataFrame(data = 
                      {
                         'product': pdf['product'].iloc[0], 
                         'wholesaler': pdf['wholesaler'].iloc[0], 
                         'date' : pd.to_datetime(series_df.index.values[-1]) + dt.timedelta(days=7), 
                         'demand' : int(abs(fcast1.iloc[-1]))
                      }, 
                          index = [0]
                     )
    return df 

# COMMAND ----------

# define schema for Spark UDF - specifies the schema of the forecasted results 

fc_schema = StructType(
  [
    StructField('product', StringType()),
    StructField('wholesaler', StringType()),
    StructField('date', DateType()),
    StructField('demand', FloatType())
  ]
)

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC Spark processes data in partitions. We want an approach combining Spark's scalability with Pandas' ease of use for time series forecasting. For this we use `applyInPandas`--> it allows us to leverage Python's  data science libraries (like statsmodels for forecasting) in a distributed Spark environment.
# MAGIC
# MAGIC How we do it (code explaantion): 
# MAGIC
# MAGIC `n_tasks = demand_df.select("product", "wholesaler").distinct().count()` --> Determine the number of unique product and wholesaler pairs. Calculate the number of tasks: each unique combination of product and wholesaler will have its own forecast. Calculating the count ensures data is optimally repartitioned for parallel processing. 
# MAGIC
# MAGIC `.repartition(n_tasks, "product", "wholesaler")` and `.groupBy("product", "wholesaler")` --> Redistribute data across partitions, ensuring efficient parallel processing. We split the data into tasks for and we redistribute the data across the n_tasks partitions using product and wholesaler as partition keys. This ensures that each unique combination of product and wholesaler are grouped in the same partition. This will optimize parallel processing for hte applyInPandas operation.
# MAGIC
# MAGIC `.applyInPandas(one_step_ahead_forecast, schema=fc_schema)` --> pandas UDF executes the one_step_ahead_forecast on each partition. one_step_ahead_forecast: a user-defined function written in Python that operates on a Pandas DataFrame. It performs the Holt-Winters forecast for each group of data. 

# COMMAND ----------

spark.conf.set("spark.databricks.optimizer.adaptive.enabled", "false")
n_tasks = demand_df.select("product", "wholesaler").distinct().count() 

forecast_df = (
  demand_df
  .repartition(n_tasks, "product", "wholesaler") # splits data into tasks for distributed processing 
  .groupBy("product", "wholesaler")
  .applyInPandas(one_step_ahead_forecast, schema=fc_schema) # pandas UDF executes the one_step_ahead_forecast on each partition
)

display(forecast_df)

# COMMAND ----------

# MAGIC %md
# MAGIC Running data integrity check: checking that the forecasting successfully handled all unique `product` and `wholesaler` combinations.

# COMMAND ----------

assert demand_df.select('product', 'wholesaler').distinct().count() == forecast_df.count()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Aggregate forecasts on distribution center level
# MAGIC
# MAGIC Using the mapping table that uniquely assigns each distribution center to a wholesaler. 
# MAGIC

# COMMAND ----------

distribution_center_to_wholesaler_mapping_table = spark.read.table(f"{catalogName}.{dbName}.distribution_center_to_wholesaler_mapping")

# COMMAND ----------

display(distribution_center_to_wholesaler_mapping_table)

# COMMAND ----------

display(forecast_df)

# COMMAND ----------

distribution_center_demand = (
  forecast_df.
  join(distribution_center_to_wholesaler_mapping_table, [ "wholesaler" ] , "left").
  groupBy("distribution_center", "product").
  agg(f.sum("demand").alias("demand"))
)                              

# COMMAND ----------

display(distribution_center_demand)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Save to delta

# COMMAND ----------

# Write the data 
distribution_center_demand.write.mode("overwrite").saveAsTable(f"{catalogName}.{dbName}.product_demand_forecasted")

# COMMAND ----------

# MAGIC %md 
# MAGIC &copy; 2023 Databricks, Inc. All rights reserved. The source in this notebook is provided subject to the Databricks License [https://databricks.com/db-license-source].  All included or referenced third party libraries are subject to the licenses set forth below.
# MAGIC
# MAGIC | library                                | description             | license    | source                                              |
# MAGIC |----------------------------------------|-------------------------|------------|-----------------------------------------------------|
# MAGIC | pulp                                 | A python Linear Programming API      | https://github.com/coin-or/pulp/blob/master/LICENSE        | https://github.com/coin-or/pulp                      |