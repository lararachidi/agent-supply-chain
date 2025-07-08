# Databricks notebook source
# Install the vector search SDK
%pip install databricks-sdk
dbutils.library.restartPython()

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
# MAGIC

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE FUNCTION _genie_query(databricks_host STRING, 
# MAGIC                   databricks_token STRING,
# MAGIC                   space_id STRING,
# MAGIC                   question STRING,
# MAGIC                   contextual_history STRING)
# MAGIC RETURNS STRING
# MAGIC LANGUAGE PYTHON
# MAGIC COMMENT 'This is a agent that you can converse with to get answers to questions. Try to provide simple questions and provide history if you had prior conversations.'
# MAGIC AS
# MAGIC $$
# MAGIC     import json
# MAGIC     import os
# MAGIC     import time
# MAGIC     from dataclasses import dataclass
# MAGIC     from datetime import datetime
# MAGIC     from typing import Optional, Union
# MAGIC     import pandas as pd
# MAGIC     import requests
# MAGIC
# MAGIC
# MAGIC     MAX_ITERATIONS = 50
# MAGIC
# MAGIC     @dataclass
# MAGIC     class GenieResponse:
# MAGIC         result: Union[str, pd.DataFrame]
# MAGIC         query: Optional[str] = ""
# MAGIC         description: Optional[str] = ""
# MAGIC         
# MAGIC         def to_string(self):
# MAGIC             if isinstance(self.result, pd.DataFrame):
# MAGIC                 result_dict = self.result.to_dict(orient="records")
# MAGIC                 result_str = json.dumps(result_dict, indent=2)
# MAGIC             else:
# MAGIC                 result_str = str(self.result)
# MAGIC             
# MAGIC             return (f"Result: {result_str}\n"
# MAGIC                     f"Query: {self.query}\n"
# MAGIC                     f"Description: {self.description}")
# MAGIC
# MAGIC     def _parse_query_result(resp) -> Union[str, pd.DataFrame]:
# MAGIC         output = resp["result"]
# MAGIC         if not output:
# MAGIC             return "EMPTY"
# MAGIC
# MAGIC         columns = resp["manifest"]["schema"]["columns"]
# MAGIC         header = [str(col["name"]) for col in columns]
# MAGIC         rows = []
# MAGIC
# MAGIC         for item in output["data_array"]:
# MAGIC             row = []
# MAGIC             for column, value in zip(columns, item):
# MAGIC                 type_name = column["type_name"]
# MAGIC                 if value is None:
# MAGIC                     row.append(None)
# MAGIC                     continue
# MAGIC
# MAGIC                 if type_name in ["INT", "LONG", "SHORT", "BYTE"]:
# MAGIC                     row.append(int(value))
# MAGIC                 elif type_name in ["FLOAT", "DOUBLE", "DECIMAL"]:
# MAGIC                     row.append(float(value))
# MAGIC                 elif type_name == "BOOLEAN":
# MAGIC                     row.append(value.lower() == "true")
# MAGIC                 elif type_name == "DATE" or type_name == "TIMESTAMP":
# MAGIC                     row.append(datetime.strptime(value[:10], "%Y-%m-%d").date())
# MAGIC                 elif type_name == "BINARY":
# MAGIC                     row.append(bytes(value, "utf-8"))
# MAGIC                 else:
# MAGIC                     row.append(value)
# MAGIC
# MAGIC             rows.append(row)
# MAGIC
# MAGIC         return pd.DataFrame(rows, columns=header)
# MAGIC
# MAGIC     class Genie:
# MAGIC         def __init__(self, space_id, host=None, token=None):
# MAGIC             self.space_id = space_id
# MAGIC             self.host = host or os.environ.get("DATABRICKS_HOST")
# MAGIC             self.token = token or os.environ.get("DATABRICKS_TOKEN")
# MAGIC             
# MAGIC             assert self.host is not None, "DATABRICKS_HOST is not set"
# MAGIC             assert self.token is not None, "DATABRICKS_TOKEN is not set"
# MAGIC             
# MAGIC             self.session = requests.Session()
# MAGIC             self.session.headers.update({
# MAGIC                 "Authorization": f"Bearer {self.token}",
# MAGIC                 "Accept": "application/json",
# MAGIC                 "Content-Type": "application/json"
# MAGIC             })
# MAGIC             self.api_prefix = "/api/2.0/genie/spaces"
# MAGIC
# MAGIC         def _make_url(self, path):
# MAGIC             return f"{self.host.rstrip('/')}/{path.lstrip('/')}"
# MAGIC
# MAGIC         def start_conversation(self, content):
# MAGIC             path = self._make_url(f"{self.api_prefix}/{self.space_id}/start-conversation")
# MAGIC             resp = self.session.post(
# MAGIC                 url=path,
# MAGIC                 json={"content": content}
# MAGIC             )
# MAGIC             return resp.json()
# MAGIC
# MAGIC         def create_message(self, conversation_id, content):
# MAGIC             path = self._make_url(f"{self.api_prefix}/{self.space_id}/conversations/{conversation_id}/messages")
# MAGIC             resp = self.session.post(
# MAGIC                 url=path,
# MAGIC                 json={"content": content}
# MAGIC             )
# MAGIC             return resp.json()
# MAGIC
# MAGIC         def poll_for_result(self, conversation_id, message_id):
# MAGIC             def poll_query_results(attachment_id, query_str, description):
# MAGIC                 iteration_count = 0
# MAGIC                 while iteration_count < MAX_ITERATIONS:
# MAGIC                     iteration_count += 1
# MAGIC                     path = self._make_url(
# MAGIC                         f"{self.api_prefix}/{self.space_id}/conversations/{conversation_id}/messages/{message_id}/attachments/{attachment_id}/query-result"
# MAGIC                     )
# MAGIC                     resp = self.session.get(url=path).json()["statement_response"]
# MAGIC                     
# MAGIC                     state = resp["status"]["state"]
# MAGIC                     if state == "SUCCEEDED":
# MAGIC                         result = _parse_query_result(resp)
# MAGIC                         return GenieResponse(result, query_str, description)
# MAGIC                     elif state in ["RUNNING", "PENDING"]:
# MAGIC                         print(f"Waiting for query result... (iteration {iteration_count})")
# MAGIC                         time.sleep(5)
# MAGIC                     else:
# MAGIC                         return GenieResponse(
# MAGIC                             f"No query result: {resp['state']}", query_str, description
# MAGIC                         )
# MAGIC                 return GenieResponse(
# MAGIC                     f"Genie query for result timed out after {MAX_ITERATIONS} iterations of 5 seconds",
# MAGIC                     query_str,
# MAGIC                     description,
# MAGIC                 )
# MAGIC
# MAGIC             def poll_result():
# MAGIC                 iteration_count = 0
# MAGIC                 while iteration_count < MAX_ITERATIONS:
# MAGIC                     iteration_count += 1
# MAGIC                     path = self._make_url(
# MAGIC                         f"{self.api_prefix}/{self.space_id}/conversations/{conversation_id}/messages/{message_id}"
# MAGIC                     )
# MAGIC                     resp = self.session.get(url=path).json()
# MAGIC                     
# MAGIC                     if resp["status"] == "COMPLETED":
# MAGIC                         attachment = next((r for r in resp["attachments"] if "query" in r), None)
# MAGIC                         if attachment:
# MAGIC                             query_obj = attachment["query"]
# MAGIC                             description = query_obj.get("description", "")
# MAGIC                             query_str = query_obj.get("query", "")
# MAGIC                             attachment_id = attachment["attachment_id"]
# MAGIC                             return poll_query_results(attachment_id, query_str, description)
# MAGIC                         if resp["status"] == "COMPLETED":
# MAGIC                             text_content = next(r for r in resp["attachments"] if "text" in r)["text"][
# MAGIC                                 "content"
# MAGIC                             ]
# MAGIC                             return GenieResponse(result=text_content)
# MAGIC                     elif resp["status"] in {"CANCELLED", "QUERY_RESULT_EXPIRED"}:
# MAGIC                         return GenieResponse(result=f"Genie query {resp['status'].lower()}.")
# MAGIC                     elif resp["status"] == "FAILED":
# MAGIC                         return GenieResponse(
# MAGIC                             result=f"Genie query failed with error: {resp.get('error', 'Unknown error')}"
# MAGIC                         )
# MAGIC                     # includes EXECUTING_QUERY, Genie can retry after this status
# MAGIC                     else:
# MAGIC                         print(f"Waiting... Status: {resp['status']} (iteration {iteration_count})")
# MAGIC                         time.sleep(5)
# MAGIC                 return GenieResponse(
# MAGIC                     f"Genie query timed out after {MAX_ITERATIONS} iterations of 5 seconds"
# MAGIC                 )
# MAGIC
# MAGIC             return poll_result()
# MAGIC
# MAGIC         def ask_question(self, question):
# MAGIC             resp = self.start_conversation(question)
# MAGIC             return self.poll_for_result(resp["conversation_id"], resp["message_id"])
# MAGIC             
# MAGIC         def ask_with_context(self, question, contextual_history="No context history"):
# MAGIC             formatted_message = f"""Use the contextual history to answer the question. The history may or may not help you. Use it if you find it relevant.
# MAGIC             Contextual History: {contextual_history}
# MAGIC             Question to answer: {question}"""
# MAGIC             resp = self.start_conversation(formatted_message)
# MAGIC             return self.poll_for_result(resp["conversation_id"], resp["message_id"])
# MAGIC
# MAGIC     assert space_id is not None, "space_id is not set"
# MAGIC     assert question is not None, "question is not set"
# MAGIC     assert contextual_history is not None, "contextual_history is not set"
# MAGIC
# MAGIC     # Initialize client and run query
# MAGIC     genie = Genie(space_id, databricks_host, databricks_token)
# MAGIC     result = genie.ask_with_context(question, contextual_history)
# MAGIC
# MAGIC     return result.to_string()
# MAGIC
# MAGIC $$;
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ### Create a Secret to add a PAT Token to the UC Function

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import ResourceAlreadyExists, ResourceDoesNotExist

w = WorkspaceClient()

scope_name = "supply_chain"
key_name   = "pat_token"
secret_val = "<add your secret here>"


# Create the scope only if it is not already defined
existing_scopes = {s.name for s in w.secrets.list_scopes()}
if scope_name not in existing_scopes:
    w.secrets.create_scope(scope=scope_name)


# Put (create or overwrite) the secret inside the scope
w.secrets.put_secret(
    scope=scope_name,
    key=key_name,
    string_value=secret_val,   # overwrite if it exists
)


# COMMAND ----------

# MAGIC %sql
# MAGIC
# MAGIC CREATE OR REPLACE FUNCTION ask_genie_pharma_gsc(question STRING COMMENT "The question to ask about the pharma supply chain dataset", contextual_history STRING COMMENT "provide relevant history to be able to answer this question, assume genie doesn\'t keep track of history. Use \'no relevant history\' if there is nothing relevant to answer the question.")
# MAGIC RETURNS STRING
# MAGIC LANGUAGE SQL
# MAGIC COMMENT 'This Agent interacts with the Genie space API to provide answers to questions about the pharma supply chain dataset.'  
# MAGIC RETURN SELECT _genie_query(
# MAGIC   "https://dbc-023ece0a-5678.cloud.databricks.com/",
# MAGIC   secret("supply_chain", "pat_token"),
# MAGIC   "<Enter Genie Room>",
# MAGIC   question, -- retrieved from function
# MAGIC   contextual_history -- retrieved from function
# MAGIC );

# COMMAND ----------

# MAGIC %md
# MAGIC # Instead you can also register a table query tool 
# MAGIC
# MAGIC Documentation: https://docs.databricks.com/en/generative-ai/agent-framework/agent-tool.html#table-query-tool

# COMMAND ----------


spark.sql(f"""CREATE OR REPLACE FUNCTION {catalog_name}.{db_name}.lookup_product_demand(
  product_name STRING COMMENT 'Name of the product whose demand data to look up',
  wholesaler_name STRING COMMENT 'Name of the wholesaler associated with the demand data'
)
RETURNS STRING
COMMENT 'Returns metadata about the historical demand for a particular product and wholesaler, including the most recent demand value and date. This information is useful for analyzing demand trends and forecasting.'
RETURN SELECT CONCAT(
    'Product: ', product, ', ',
    'Wholesaler: ', wholesaler, ', ',
    'Date: ', CAST(date AS STRING), ', ',
    'Demand: ', CAST(demand AS STRING)
  )
  FROM {catalog_name}.{db_name}.product_demand_historical
  WHERE product = product_name AND wholesaler = wholesaler_name
  ORDER BY date DESC
  LIMIT 1""")

# COMMAND ----------

# MAGIC %md
# MAGIC # You can search the Vector Index 

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ### Query the vector index (testing)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT string(collect_set(Content)) 
# MAGIC FROM vector_search(index => "${catalog_name}.${db_name}.email_content_index", query => 'What are the delays with distribution center 5', num_results => 5);
# MAGIC

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE FUNCTION query_unstructured_emails(question STRING COMMENT "The question to ask about supply chain")
# MAGIC RETURNS STRING
# MAGIC LANGUAGE SQL
# MAGIC COMMENT 'emails sent by the distribution centers to wholesalers explaining the delays' 
# MAGIC RETURN SELECT string(collect_set(Content)) from vector_search(index => "${catalog_name}.${db_name}.email_content_index", query => question, num_results => 5);

# COMMAND ----------

# MAGIC %md
# MAGIC # Execute Code

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE FUNCTION execute_code_sandbox(
# MAGIC   raw_code STRING COMMENT 'proper python code to be executed, this will run with the exec command',
# MAGIC   return_variable_name STRING COMMENT 'variable name to return from the code as a string'
# MAGIC   )
# MAGIC   RETURNS STRING
# MAGIC   LANGUAGE PYTHON
# MAGIC   COMMENT 'execute arbitrary python code and pick a variable that you want to be returned; use this when you think you can use python to give precise/accurate answers, for any time you want to use math; make your code compatible with python -c'
# MAGIC   AS $$
# MAGIC     import inspect
# MAGIC     import io
# MAGIC     import sys
# MAGIC     from typing import Optional
# MAGIC
# MAGIC     from pydantic import BaseModel
# MAGIC
# MAGIC
# MAGIC     class SandboxCodeExecutionResults(BaseModel):
# MAGIC         raw_code: str
# MAGIC         return_variable: str
# MAGIC         available_variables: dict[str, str]
# MAGIC         stdout_output: str = ""
# MAGIC         stderr_output: str = ""
# MAGIC         return_variable_as_string: Optional[str] = None
# MAGIC
# MAGIC
# MAGIC     def execute_code(raw_code: str, return_variable: Optional[str] = None) -> SandboxCodeExecutionResults:
# MAGIC         old_stdout = sys.stdout
# MAGIC         old_stderr = sys.stderr
# MAGIC         new_stdout = io.StringIO()
# MAGIC         new_stderr = io.StringIO()
# MAGIC         sys.stdout = new_stdout
# MAGIC         sys.stderr = new_stderr
# MAGIC
# MAGIC         local_globals = {}
# MAGIC         try:
# MAGIC             exec(raw_code, local_globals)
# MAGIC         except Exception as e:
# MAGIC             print(f"Exception: {e}", file=new_stderr)
# MAGIC
# MAGIC         sys.stdout = old_stdout
# MAGIC         sys.stderr = old_stderr
# MAGIC
# MAGIC         stdout_output = new_stdout.getvalue()
# MAGIC         stderr_output = new_stderr.getvalue()
# MAGIC
# MAGIC         available_variables = {str(k): f"Type: {type(v)} Value: {str(v)}" for k, v in local_globals.items()
# MAGIC                             if not k.startswith("__") and not k in ["raw_code", "return_variable"]
# MAGIC                             and not inspect.ismodule(v) and not inspect.isfunction(v) and not inspect.isclass(v)}
# MAGIC
# MAGIC         return SandboxCodeExecutionResults(
# MAGIC             raw_code=raw_code,
# MAGIC             return_variable=return_variable,
# MAGIC             available_variables=available_variables,
# MAGIC             stdout_output=stdout_output,
# MAGIC             stderr_output=stderr_output,
# MAGIC             return_variable_as_string=str(local_globals.get(return_variable)) if return_variable else None,
# MAGIC         )
# MAGIC     
# MAGIC     return execute_code(raw_code, return_variable_name).json()
# MAGIC   $$
# MAGIC

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT execute_code_sandbox(
# MAGIC   'numbers = [45, 678, 3567, 457]\naverage = sum(numbers) / len(numbers)',
# MAGIC   'average')

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE ${catalog_name}.${db_name}.product_demand_historical