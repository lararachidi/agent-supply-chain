# Databricks notebook source
dbutils.widgets.text('catalogName',  'main' , 'Catalog Name')
dbutils.widgets.text('dbName',  'supply_chain_db' , 'Database Name')

# COMMAND ----------

dbName = dbutils.widgets.get('dbName')
catalogName = dbutils.widgets.get('catalogName')

# COMMAND ----------

import os
import random
import pyspark.sql.functions as f
from pyspark.sql.types import FloatType

# COMMAND ----------

from pyspark.sql import functions as f

# Assuming catalogName and dbName are defined elsewhere in your code
demand_raw_df = spark.read.table(f"{catalogName}.{dbName}.raw_material_demand")
demand_df = (
     demand_raw_df   
    .groupBy("raw", "product")
    .agg(f.sum("demand_raw").alias("demand_raw"))
)
all_skus = demand_df.select('product').distinct().rdd.flatMap(lambda x: x).collect()
material_shortages_sku = random.sample(all_skus, 2)  # Directly use the list here
all_raw = demand_df.filter(f.col("product").isin(material_shortages_sku)).select('RAW').distinct().rdd.flatMap(lambda x: x).collect()
material_shortages_raw = random.sample(all_raw, 3)  # Directly use the list here

# COMMAND ----------

def random_fraction(z, minimum, maximum):
  return(random.uniform(minimum, maximum))

random_fraction_shortage_UDF = udf(lambda z: random_fraction(z, 0.5, 0.9), FloatType())
random_fraction_surplus_UDF = udf(lambda z: random_fraction(z, 0.1, 1.5), FloatType())

# COMMAND ----------

material_shortage_df = (
    demand_df.
    filter((f.col("product").isin(material_shortages_sku)) & (f.col("RAW").isin(material_shortages_raw))).
    withColumn("fraction", random_fraction_shortage_UDF(  f.col("Demand_Raw")  )).
    withColumn("supply", f.floor(f.col("fraction") * f.col("Demand_Raw"))).
    select("raw", "supply")
)
material_surplus_df = (
    demand_df.
    filter(~(f.col("product").isin(material_shortages_sku)) & (~f.col("RAW").isin(material_shortages_raw))).
    withColumn("fraction", random_fraction_surplus_UDF(  f.col("Demand_Raw")  )).
    withColumn("supply", f.floor(f.col("fraction") * f.col("Demand_Raw"))).
    select("raw", "supply")
)

# COMMAND ----------

# Write the data 
material_shortage_df.union(material_surplus_df).write \
.mode("overwrite") \
.saveAsTable(f"{catalogName}.{dbName}.raw_material_supply")

# COMMAND ----------

