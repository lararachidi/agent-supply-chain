# Supply Chain Optimization with Databricks

This project demonstrates a supply chain optimization solution for distribution networks using Databricks, with 3 manufacturing plants delivering 30 product SKUs to 5 distribution centers, which in turn serve 30-60 wholesalers each. The solution leverages Databricks' distributed computing capabilities to answer questions such as: How much revenue is at risk if we can’t produce the forecasted amount of product autoclave_1?

## Architecture

The solution follows this workflow:
- **Demand Forecasting**: Generate one-week-ahead forecasts for each product/wholesaler combination
- **Demand Aggregation**: Aggregate forecasts at distribution center level
- **Raw Material Planning**: Convert finished product demand into raw material requirements using graph-based BOM analysis
- **Transportation Optimization**: Minimize shipping costs between plants and distribution centers using linear programming

## Getting Started

1. **Set up a Databricks workspace**
- Ensure that you have permissions to write to a catalog and create and/or use a cluster 
2. **Create and/or start your cluster** 
- This solution has been tested on the following Databricks cluster configuration:
  - Cluster Type: Personal Compute
  - Access Mode: Dedicated (formerly: Single user)
  - Databricks Runtime Version: 16.3 ML (includes Apache Spark 3.5.2, Scala 2.12)
  - Node Type: i3.xlarge (30.5 GB Memory, 4 Cores)
3. **Import all notebooks into your workspace**
- In the workspace tab, under your user name follow these steps (recommended): 
- Create a Git folder
- Add the Git repository URL
- Alternatively, you can do right click and import the notebooks one by one, however it is recommended to add the Git repository URL instead
4. **Run `01_Introduction_And_Setup.py` to initialize the environment and generate sample data**
- The notebooks use widgets for configuration:
  - `catalog_name`: Databricks catalog name (default: "main")
  - `db_name`: Database name (default: "supply_chain_db")
5. **You have two options to run the subsequent notebooks**
- Option 1: Run all subsequent notebooks at once below by using a magic command.
- Option 2: Run each subsequent notebook manually in numerical order to follow the end-to-end process


## Supply chain data

Supporting resource notebooks:
- `_resources/00-setup.py`: Configuration setup
- `_resources/01-data-generator.py`: Generate synthetic supply chain data
- `_resources/02-generate-supply.py`: Generate supply data

These resource notebooks will create the following tables that we will leverage to build our solution:
- `product_demand_historical`: Historical product demand by wholesaler
- `distribution_center_to_wholesaler_mapping`: Mapping between distribution centers and wholesalers
- `bom`: Bill of materials with material relationships
- `plant_supply`: Maximum supply capacity by plant and product
- `transport_cost`: Transportation costs between plants and distribution centers
- `list_prices`: Price for each product 


## Notebooks

The solution consists of multiple Databricks notebooks:

1. **`01_Introduction_And_Setup.py`**: 
- Project overview and data setup. 
- Make sure to run it first and to then run each notebook sequentially.
2. **`02_Fine_Grained_Demand_Forecasting.py`**: 
- Time series forecasting generating one-week-ahead SKU demand for every wholesaler and distribution center with a Holt-Winters seasonal model. 
- The output is a table `product_demand_forecasted` with aggregate forecasts at the distribution center level 
3. **`03_Derive_Raw_Material_Demand.py`**: 
- In this notebook, we process product demand forecasts to determine raw material requirements using a graph-based approach (by transforming the BOM data into graph edges). 
- The outputs are two tables: `raw_material_demand` and `raw_material_supply`
4. **`04_Optimize_Transportation.py`**: 
- Linear programming to minimize transportation costs
- The output is the table `shipment_recommendations` 
5. **`05_Data_Analysis_&_Functions.py`**: 
- Additional analysis and utility functions: the notebook identifies critical materials with supply shortages by comparing demand vs. supply data & analyzes hierarchical relationships between materials and products
- As output, you get the following custom SQL Functions:
  - `product_from_raw`: Maps a raw material to all downstream products
  - `raw_from_product`: Maps a product to all upstream raw materials
  - `revenue_risk`: Calculates potential revenue impact from raw material shortages
6. **`06_Vector_Search.py`**: 
- Generates supply-chain manager e-mails (unstructured data) and store the data in a vector index, enabling semantic queries that surface delay and risk signals 
7. **`07_More_Functions.py`**: 
- Extended functionality and utilities
- As output, you get the following custom SQL Functions: 
  - `lookup_product_demand`: Retrieves historical demand data for specific products and wholesalers
  - `query_unstructured_emails`: Searches emails using vector search for relevant supply chain information
  - `execute_code_sandbox`: Enables dynamic code execution for custom analysis
  - `_genie_query`: Core function that interfaces with Databricks Genie API
  - `ask_genie_pharma_gsc`: Natural language interface to query the supply chain dataset
- Make sure to customize the Genie integration:
   - Update the Databricks host URL and token
   - Specify your Genie Space ID
  

## Creating Your Own Agent

- To create a supply chain agent, you can leverage these functions in any AI agent orchestrator as shown in this demo video: https://www.youtube.com/watch?v=cz-x2B31Ga8
- Test your Agent with the following questions: 
  - What products are dependent on L6HUK material?
  - How much revenue is at risk if we can’t produce the forecasted amount of product autoclave_1?
  - Which products have delays right now?
  - Are there any delays with syringe_1? 
  - What raw materials are required for syringe_1?
  - Are there any shortages with one of the following raw materials: O4GRQ, Q5U3A, OAIFB or 58RJD?
  - What are the delays associated with wholesaler 9?


- You can also use SQL functions to query your supply chain: 
   ```sql
   SELECT query_unstructured_emails(
     'What delivery delays are affecting Distribution Center 3?'
   );
   ```

## Acknowledgments

- This project is based on Databricks' supply chain optimization solution accelerator available at: https://github.com/databricks-industry-solutions/supply-chain-optimization. 
- I augmented this initial accelerator with functions to make it agentic and synthetic data for the vector index. 
- Thanks to Puneet Jain for modularizing the notebooks! 
- For more information about this solution accelerator, visit https://www.databricks.com/solutions/accelerators/supply-chain-distribution-optimization.
