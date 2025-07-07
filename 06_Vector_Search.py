# Databricks notebook source
# MAGIC %md
# MAGIC ## Dependencies 

# COMMAND ----------

# Install the vector search SDK
%pip install databricks-vectorsearch
dbutils.library.restartPython()

# COMMAND ----------

from databricks.sdk import WorkspaceClient, errors

try:
    WorkspaceClient().secrets.get_secret(
        scope="my_openai_secret_scope",
        key="openai_api_key"
    )
except errors.ResourceDoesNotExist:
    raise RuntimeError(
        "Secret `my_openai_secret_scope/openai_api_key` not found. "
        "Run 01_Introduction_And_Setup.py first, or create it manually."
    )

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

# MAGIC %md
# MAGIC ## Generate email data and store it in table  

# COMMAND ----------

from datetime import datetime, timedelta
import random

# Define the date range
start_date = datetime.fromisoformat("2022-11-28T00:00:00.000+00:00")
end_date = datetime.fromisoformat("2024-11-25T00:00:00.000+00:00")

# Function to generate random dates
def generate_random_date(start, end):
    return start + timedelta(seconds=random.randint(0, int((end - start).total_seconds())))

# Generate 10 email examples with fully randomized parameters
email_examples_random = []
for i in range(500):
    # Generate random parameters
    random_date = generate_random_date(start_date, end_date).isoformat()
    distribution_center = random.randint(1, 5)
    wholesaler = random.randint(1, 30)
    avg_delay = round(random.uniform(2.5, 5.5), 1)
    baseline_delay = round(avg_delay - random.uniform(0.5, 1.5), 1)
    syringe_units = random.randint(100, 500)
    crimper_units = random.randint(50, 300)
    delay_percentage = random.randint(40, 80)
    days_saved = round(random.uniform(0.5, 2.5), 1)
    route = random.choice(["33C", "45B", "27A"])

    # Create email content
    email_content = f"""
Subject: Delivery Delays: Distribution Center {distribution_center} to Wholesaler {wholesaler}  

Date: {random_date}  

Dear Team,  

We've identified consistent delays in deliveries from Distribution Center {distribution_center} to Wholesaler {wholesaler}, impacting our supply chain performance. Key issues include:  

1. Average Delay: Deliveries are taking {avg_delay} days, exceeding the baseline of {baseline_delay} days.  
2. Impact: Stockouts of {syringe_units} units of syringe_1 and {crimper_units} units of vial crimper_2 have occurred due to mismatched inventory and demand.  
3. Frequency: {delay_percentage}% of shipments in the last 8 weeks have been delayed.  

Next Steps:  
- Route Review: Explore alternatives (e.g., Route {route}) to save {days_saved} days per shipment.  
- Process Audit: Review dispatch procedures at Distribution Center {distribution_center} for bottlenecks.  
- Real-Time Tracking: Implement proactive monitoring for faster issue resolution.  

Please share additional insights or concerns to support resolution. I'll follow up within 5 days to align on progress.  

Best regards,  
John Smith  
Supply Chain Optimization Manager  
"""
    email_examples_random.append((random_date, email_content.strip()))

# Create a DataFrame
df_emails_random = spark.createDataFrame(email_examples_random, schema=["Date", "Content"])

# Save to a table
df_emails_random.write.saveAsTable(f"{catalog_name}.{db_name}.emails_distribution_center_to_wholesaler", mode="overwrite", format="delta", header=True)

# COMMAND ----------

spark.sql(f"ALTER TABLE {catalog_name}.{db_name}.`emails_distribution_center_to_wholesaler` SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")

# COMMAND ----------

# MAGIC %md
# MAGIC Display the table

# COMMAND ----------

df_emails_random_spark = spark.read.table(f"{catalog_name}.{db_name}.emails_distribution_center_to_wholesaler")
display(df_emails_random_spark.limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create an endpoint for the vector index 
# MAGIC Creating a vector index will allow us to perform semantic similarity searches on the email content using Databricks Vector Search.

# COMMAND ----------

from databricks.vector_search.client import VectorSearchClient
import os

# Initialize the Vector Search client
vs_client = VectorSearchClient()

# Get the current endpoint or create one if it doesn't exist
def get_or_create_endpoint(endpoint_name):
    try:
        endpoints = vs_client.list_endpoints().get("endpoints", [])
        for endpoint in endpoints:
            if endpoint.get("name") == endpoint_name:
                print(f"Using existing endpoint: {endpoint_name}")
                return endpoint_name
    except Exception as e:
        print(f"Error listing endpoints: {e}")
    
    # Create endpoint if it doesn't exist
    print(f"Creating new endpoint: {endpoint_name}")
    vs_client.create_endpoint(
        name=endpoint_name,
        endpoint_type="STANDARD"
    )
    return endpoint_name

# Get or create the vector search endpoint
endpoint_name = "supply-chain-endpoint"
current_endpoint_name = get_or_create_endpoint(endpoint_name)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create embedding model endpoint 
# MAGIC
# MAGIC Note that instead of using a secret, you could also just copy / paste your API key but we strongly recommend to use secrets. 
# MAGIC
# MAGIC If you don't want to use secrets, instead of 
# MAGIC
# MAGIC `"openai_api_key": "{{secrets/my_openai_secret_scope/openai_api_key}}"`
# MAGIC
# MAGIC you can use: 
# MAGIC
# MAGIC `"openai_api_key_plaintext": "sk-yourApiKey"`
# MAGIC

# COMMAND ----------

import mlflow.deployments

# COMMAND ----------

from mlflow.deployments import get_deploy_client

# Initialise the Databricks MLflow deployment client
client = get_deploy_client("databricks")

# Reuse the endpoint if it exists, otherwise create it
def get_or_create_endpoint(endpoint_name: str) -> str:
    try:
        for ep in client.list_endpoints():          # check existing endpoints
            if ep.get("name") == endpoint_name:
                print(f"Using existing endpoint: {endpoint_name}")
                return endpoint_name
    except Exception as e:
        print(f"Error listing endpoints: {e}")

    # Create the endpoint only if it wasn't found
    print(f"Creating new endpoint: {endpoint_name}")
    client.create_endpoint(
        name=endpoint_name,
        config={
            "served_entities": [
                {
                    "name": "openai_embeddings",
                    "external_model": {
                        "name": "text-embedding-3-large",
                        "provider": "openai",
                        "task": "llm/v1/embeddings",
                        "openai_config": {
                            "openai_api_key": "{{secrets/my_openai_secret_scope/openai_api_key}}" # replace with your own secret 
                        }
                    }
                }
            ]
        }
    )
    return endpoint_name

# Use the helper
endpoint_name = "supply-chain-embedding"
current_embedding_endpoint_name = get_or_create_endpoint(endpoint_name)
print(f"Ready to serve: {current_endpoint_name}")


# COMMAND ----------

# MAGIC %md
# MAGIC ## Create a Vector Index (Vector Search)

# COMMAND ----------

# Create a vector index 
def create_vector_search_index(name,source_table_fullname):
    # Define the index configuration
    index_config = {
        "index_name": name,
        "endpoint_name": current_endpoint_name,
        "primary_key": "Date",  # Using Date as the primary key
        "embedding_model_endpoint_name": current_embedding_endpoint_name,  # Using OpenAI embedding model,
        "embedding_source_column": "Content",
        "pipeline_type" : "CONTINUOUS", # Can be changed to TRIGGERED 
        "source_table_name": source_table_fullname
    }
    
    try:
        # Check if index already exists
        try:
            existing_index = vs_client.get_index(
                endpoint_name=current_endpoint_name,
                index_name=name
            )
            print(f"Index {name} already exists")
            return existing_index
        except:
            # Create the index
            print(f"Creating vector search index: {name}")
            index_name =vs_client.create_delta_sync_index(**index_config)
            return index_name
    except Exception as e:
        print(f"Error creating index: {e}")
        return None

# Create the vector search index
name = f"{catalog_name}.{db_name}.email_content_index"
source_table_fullname = f"{catalog_name}.{db_name}.emails_distribution_center_to_wholesaler"
index_name = create_vector_search_index(name,source_table_fullname)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Query the Vector Index
# MAGIC Below is an example of how to perform a vector similarity search using the created index. You can uncomment to run the cell.

# COMMAND ----------

# Example of how to perform a vector search
def vector_similarity_search(index_name ,query_text, num_results=5):
    try:
        # Perform the vector search
        results = index_name.similarity_search(
            query_text = query_text,
            num_results=num_results,
            columns=["Date", "Content"]
        )
        
        # Convert results to a DataFrame for display
        matches = results['result'].get("data_array", [])
        if matches:
            result_df = spark.createDataFrame(results['result']['data_array'], ["Date", "Content", "Similarity Score"])
            return result_df
        else:
            print("No results found")
            return None
    except Exception as e:
        print(f"Error performing similarity search: {e}")
        return None

# COMMAND ----------

# Test function with a sample query
vector_similarity_search(index_name ,"delays in delivery to distribution center 2").display()