# Databricks notebook source
# MAGIC %md
# MAGIC This project is based on Databricks' supply chain optimization solution accelerator available at: https://github.com/databricks-industry-solutions/supply-chain-optimization. For more information about this solution accelerator, visit https://www.databricks.com/solutions/accelerators/supply-chain-distribution-optimization.

# COMMAND ----------

# MAGIC %md
# MAGIC # Derive Raw Material Demand
# MAGIC
# MAGIC In this notebook, we process product demand forecasts to determine raw material requirements using a graph-based approach.
# MAGIC

# COMMAND ----------

# MAGIC %pip install networkx --quiet
# MAGIC %pip install graphframes --quiet
# MAGIC %restart_python

# COMMAND ----------

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
import string
import networkx as nx
import random
import numpy as np
from graphframes import *
from graphframes.lib import *
AM = AggregateMessages
from pyspark.sql.types import StructType, StructField, StringType, ArrayType, StringType, LongType

# COMMAND ----------

# MAGIC %md
# MAGIC Read the product_demand_forecasted Delta table that we just created. We retrieve the forecasted demand as an input for subsequent calculations. 
# MAGIC
# MAGIC Read the BOM (bill of materials) which contains the relationship between products and raw materials. This allows us to derive raw material demand. 

# COMMAND ----------

demand_df = spark.read.table(f"{catalogName}.{dbName}.product_demand_forecasted").select("product", "demand")
bom = spark.read.table(f"{catalogName}.{dbName}.bom")

# COMMAND ----------

# MAGIC %md
# MAGIC We transforms the BOM data into graph edges:
# MAGIC * material_in: Source node (raw material).
# MAGIC * material_out: Destination node (finished product).

# COMMAND ----------

edges = (bom.
  withColumnRenamed("material_in","src"). 
  withColumnRenamed("material_out","dst")
)
display(edges)       

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC We define a function to extract unique nodes (src and dst) and convert them into graph vertices.

# COMMAND ----------

import pyspark.sql.functions as f
def create_vertices_from_edges(edges):
  vertices = ((edges.
   select(f.col('src')).
   distinct().
   withColumnRenamed('src','id')).
 union(
    (edges.
     select(f.col('dst')).
     distinct().
     withColumnRenamed('dst','id'))
 ).distinct()
 )
  return(vertices)

# COMMAND ----------

vertices = create_vertices_from_edges(edges)
display(vertices)

# COMMAND ----------

# MAGIC %md
# MAGIC We build the graph, we create a GraphFrame object using vertices and edges 

# COMMAND ----------

g = GraphFrame(vertices, edges)

# COMMAND ----------

# MAGIC %md
# MAGIC We derive relationships in the graph with a function that tracks which materials are required for specific products 

# COMMAND ----------

def get_sku_for_raw(gx):
  
  # Initiate Iteration
  iteration = 1
  
  # Initiate the edges - initialize graph structures 
  updated_edges = gx.edges.select(f.col("src"),f.col("dst")).withColumn("aggregated_parents", f.col("dst"))
  updated_edges = updated_edges.localCheckpoint()
 
  # Initiate the vertices
  updated_vertices = gx.vertices
  updated_vertices = updated_vertices.localCheckpoint()
  
  # Initiate the graph
  g_for_loop = GraphFrame(updated_vertices, updated_edges)
  
  # Initiate vertices_with_agg_messages
  emptyRDD = spark.sparkContext.emptyRDD()
  schema = StructType([
    StructField('id', StringType(), True),
    StructField('aggregated_parents_from_parent', ArrayType(StringType(), True)),
    StructField('iteration', LongType(), True)
  ])
  vertices_with_agg_messages = spark.createDataFrame(emptyRDD,schema)
  
  
  while(True):
    
    ####THE WHILE LOOP STARTS HERE############################################################################
    
    #Aggregated Messaging - implements a graph traversal to pass information  
    msgToSrc = AM.edge["aggregated_parents"]

    agg = g_for_loop.aggregateMessages(
     f.collect_set(AM.msg).alias("aggregated_parents_from_parent"),
     sendToSrc=msgToSrc,
     sendToDst=None
    )

    agg = agg.withColumn("iteration", f.lit(iteration))

    if (iteration > 1):
      agg = agg.withColumn("aggregated_parents_from_parent",f.flatten(f.col("aggregated_parents_from_parent")))


    vertices_with_agg_messages = vertices_with_agg_messages.union(agg) # retains only the furthest aggregation results for each node 
    
    #Increase iteration
    iteration+=1
    
    #Update edges
    updated_edges = g_for_loop.edges
    updated_edges = (updated_edges.
      join(agg, updated_edges["dst"] == agg["id"], how="inner").
      select(f.col("src"), f.col("dst"), f.col("aggregated_parents_from_parent")).
      withColumnRenamed("aggregated_parents_from_parent", "aggregated_parents").
      withColumn("aggregated_parents", f.array_union(f.col("aggregated_parents"), f.array(f.col("dst")))).
      select(f.col("src"), f.col("dst"), f.col("aggregated_parents"))
    )
    
    if (updated_edges.count() == 0):
      break
    
    # Checkpoint
    updated_vertices = updated_vertices.localCheckpoint()
    updated_edges = updated_edges.localCheckpoint()
    
    #Update the graph
    g_for_loop = GraphFrame(updated_vertices, updated_edges)
    
    ####THE WHILE LOOP ENDS HERE#######################################################################
    
  # Subset to final iteration per id
  helper = (vertices_with_agg_messages.
    groupBy("id").
    agg(f.max("iteration").alias("iteration")))
  # this is the output giving relationshiops between raw materials and the products they contribute to 
  vertices_with_agg_messages = helper.join(vertices_with_agg_messages, ["id", "iteration"],  how="inner")

  # Subset to furthermost children
  in_degrees_df = gx.inDegrees
  raw_df = (vertices.
   join( in_degrees_df, ["id"], how='left_anti'))
  vertices_with_agg_messages = (raw_df.
                               join(vertices_with_agg_messages, ["id"],how="inner").select(f.col("id"),f.col("aggregated_parents_from_parent"))
                              )
  vertices_with_agg_messages = (vertices_with_agg_messages.
                                 withColumn("product", f.col("aggregated_parents_from_parent").getItem(0)).
                                 select(f.col("id"), f.col("product"))
                              )
    
    
  return(vertices_with_agg_messages)

# COMMAND ----------

res1 = get_sku_for_raw(g)
display(res1)

# COMMAND ----------

# MAGIC %md
# MAGIC Calculate quantity of raw materials needed for specific products 

# COMMAND ----------

def get_quantity_of_raw_needed_for_its_fin(gx):
  # Initialization:
  msgToSrc = AM.edge["qty"]
  
  # Initiate the graph to be updated by each loop iteration
  vertices = gx.vertices 
  edges = gx.edges
  vertices = vertices.localCheckpoint()
  edges = edges.localCheckpoint()
  
  g_for_loop = gx
  
  # initiate vertices_with_agg_messages
  emptyRDD = spark.sparkContext.emptyRDD()
  schema = StructType([
    StructField('id', StringType(), True),
    StructField('qty', LongType(), True),
    StructField('iteration', LongType(), True)
  ])
  vertices_with_agg_messages = spark.createDataFrame(emptyRDD,schema)
  
  #Initialize the iteration integer
  iteration = 1
  
  while(True):
    #Pass edge qty to child vertex
    agg = g_for_loop.aggregateMessages(
     f.first(AM.msg).alias("qty_from_parent"),
     sendToSrc=msgToSrc,
     sendToDst=None
    )
    
    #Update aggregation information table
    agg = agg.withColumn("iteration", f.lit(iteration))
    vertices_with_agg_messages = vertices_with_agg_messages.union(agg)
    
    #Update edges accordingly
    edges_old = g_for_loop.edges
    
    helper = (edges_old.
       join(agg, edges_old['dst'] == agg['id'], "left").
       filter(f.col("id").isNull()).
       select(f.col("src")).
       withColumnRenamed("src","to_multiply_look_up")
       )
    
    edges_update = edges_old.join(agg, edges_old['dst'] == agg['id'], "inner")
    edges_update = (edges_update.
           join(helper, edges_update["dst"] == helper["to_multiply_look_up"], "left").
                withColumn("qty", f.when(f.col("to_multiply_look_up").isNull(), f.col("qty")  ).otherwise(f.col("qty")*f.col("qty_from_parent"))).
                select(f.col('src'),f.col('dst'),f.col('qty'))
               )
    
    #Formulate Break condition
    if (edges_update.count()==0):
      break
      
    #Update iteration
    iteration+=1
    
    #Checkpoint
    edges_update = edges_update.localCheckpoint()
    
    #Update Graph
    g_for_loop = GraphFrame(vertices, edges_update)
  
  #Subset to final iteration per id
  helper = (vertices_with_agg_messages.
    groupBy("id").
    agg(f.max("iteration").alias("iteration"))
         )
  # provides the total quantity of raw materials required 
  vertices_with_agg_messages = helper.join(vertices_with_agg_messages, ["id", "iteration"],  how="inner")

  # Subset to furthermost children
  in_degrees_df = g.inDegrees
  raw_df = (vertices.
   join( in_degrees_df, ["id"], how='left_anti' )
  )
  vertices_with_agg_messages = raw_df.join(vertices_with_agg_messages, ["id"], how="inner").select(f.col("id"),f.col("qty"))
    
  #Return
  return(vertices_with_agg_messages)

# COMMAND ----------

res2 = get_quantity_of_raw_needed_for_its_fin(g)
display(res2)

# COMMAND ----------

# MAGIC %md
# MAGIC Combine the results, relationships (res1) and quantities (res2) into a single table.

# COMMAND ----------

aggregated_bom = (res1.
                    join(res2, ["id"], how="inner").
                    withColumnRenamed("id","RAW").
                    withColumnRenamed("qty","QTY_RAW").
                    orderBy(f.col("product"),f.col("RAW"))
                 )
display(aggregated_bom)

# COMMAND ----------

# MAGIC %md
# MAGIC Calculate raw material demand: computes teh raw material demand by multiplying raw material quantities with forecasted product demand

# COMMAND ----------

demand_raw_df = (demand_df.
      join(aggregated_bom, ["product"], how="inner").
      withColumn("Demand_Raw", f.col("QTY_RAW")*f.col("Demand")).
      withColumnRenamed("Demand","Demand_product").
      orderBy(f.col("product"),f.col("RAW"))
)
display(demand_raw_df)

# COMMAND ----------

# MAGIC %md
# MAGIC Save the raw material demand as a table 

# COMMAND ----------

# Write the data 
demand_raw_df.write.mode("overwrite").saveAsTable(f"{catalogName}.{dbName}.raw_material_demand")

# COMMAND ----------

# MAGIC %md
# MAGIC Execute next notebook to generate supply data 

# COMMAND ----------

import os
notebook_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
notebook_path = os.path.join(os.path.dirname(notebook_path),"_resources/02-generate-supply")
dbutils.notebook.run(notebook_path, 600, {"dbName": dbName, "catalogName": catalogName})

# COMMAND ----------

raw_material_supply_df = spark.read.table(f"{catalogName}.{dbName}.raw_material_supply")
raw_material_supply_df.display()

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2023 Databricks, Inc. All rights reserved. The source in this notebook is provided subject to the Databricks License [https://databricks.com/db-license-source].  All included or referenced third party libraries are subject to the licenses set forth below.
# MAGIC
# MAGIC | library                                | description             | license    | source                                              |
# MAGIC |----------------------------------------|-------------------------|------------|-----------------------------------------------------|
# MAGIC | pulp                                 | A python Linear Programming API      | https://github.com/coin-or/pulp/blob/master/LICENSE        | https://github.com/coin-or/pulp                      |