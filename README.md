# Supply Chain Optimization with Databricks

A comprehensive supply chain optimization agentic solution for distribution networks using Databricks.

## Project Overview

This project demonstrates a supply chain optimization solution, with 3 manufacturing plants delivering 30 product SKUs to 5 distribution centers, which in turn serve 30-60 wholesalers each. The solution leverages Databricks' distributed computing capabilities to:

1. Generate realistic supply chain data
2. Perform demand forecasting at granular levels
3. Analyze bill of materials (BOM) to derive raw material requirements
4. Optimize transportation costs across the network

## Architecture

The solution follows this workflow:
- **Demand Forecasting**: Generate one-week-ahead forecasts for each product/wholesaler combination
- **Demand Aggregation**: Aggregate forecasts at distribution center level
- **Raw Material Planning**: Convert finished product demand into raw material requirements using graph-based BOM analysis
- **Transportation Optimization**: Minimize shipping costs between plants and distribution centers using linear programming

## Cluster Configuration

This solution has been tested on the following Databricks cluster configuration:

- **Cluster Type**: Personal Compute
- **Access Mode**: Dedicated (formerly: Single user)
- **Databricks Runtime Version**: 16.3 ML (includes Apache Spark 3.5.2, Scala 2.12)
- **Node Type**: i3.xlarge (30.5 GB Memory, 4 Cores)


## Notebooks

The solution consists of multiple Databricks notebooks:

1. `01_Introduction_And_Setup.py`: Project overview and data setup
2. `02_Fine_Grained_Demand_Forecasting.py`: Time series forecasting using Holt-Winters method
3. `03_Derive_Raw_Material_Demand.py`: Graph-based analysis to calculate raw material requirements
4. `04_Optimize_Transportation.py`: Linear programming to minimize transportation costs
5. `05_Data_Analysis_&_Functions.py`: Additional analysis and utility functions
6. `06_Generate_Unstructured_Data.py`: Generate sample unstructured data
7. `07_More_Functions.py`: Extended functionality and utilities

Supporting resource notebooks:
- `_resources/00-setup.py`: Configuration setup
- `_resources/01-data-generator.py`: Generate synthetic supply chain data
- `_resources/02-generate-supply.py`: Generate supply data

## Technology Stack

- **Databricks**: Unified analytics platform
- **PySpark**: Distributed data processing
- **MLlib**: Distributed machine learning
- **GraphFrames/NetworkX**: Graph processing for BOM analysis
- **PuLP**: Linear programming solver for transportation optimization
- **statsmodels**: Time series forecasting libraries

## Getting Started

1. Set up a Databricks workspace
2. Import all notebooks into your workspace
3. Run `01_Introduction_And_Setup.py` to initialize the environment and generate sample data
4. Run each subsequent notebook in numerical order to follow the end-to-end process

## Configuration

The notebooks use widgets for configuration:
- `catalog_name`: Databricks catalog name (default: "supply_chain")
- `db_name`: Database name (default: "supply_chain_db")

## AI Agents and Advanced Analytics

The project includes several AI agent capabilities for advanced supply chain analytics:

### Supply Chain Analysis Functions (05_Data_Analysis_&_Functions.py)

- **Raw Material Analysis**: Identifies critical materials with supply shortages by comparing demand vs. supply data
- **BOM Relationship Mapping**: Analyzes hierarchical relationships between materials and products
- **Custom SQL Functions**:
  - `product_from_raw`: Maps a raw material to all downstream products
  - `raw_from_product`: Maps a product to all upstream raw materials
  - `revenue_risk`: Calculates potential revenue impact from raw material shortages

### Unstructured Data Analysis (06_Generate_Unstructured_Data.py)

- **Email Generation**: Creates synthetic email data about supply chain delays
- **Vector Search Integration**: 
  - Creates a vector index on email content using Databricks Vector Search
  - Enables semantic search on supply chain communications
  - Uses the `databricks-vectorsearch` SDK for embedding and retrieval

### Agent Creation and Integration (07_More_Functions.py)

- **Databricks Genie Integration**:
  - `_genie_query`: Core function that interfaces with Databricks Genie API
  - `ask_genie_pharma_gsc`: Natural language interface to query the supply chain dataset
  
- **Custom Analysis Functions**:
  - `lookup_product_demand`: Retrieves historical demand data for specific products and wholesalers
  - `query_unstructured_emails`: Searches emails using vector search for relevant supply chain information
  - `execute_code_sandbox`: Enables dynamic code execution for custom analysis

### Creating Your Own Agent

To create a supply chain agent:

1. Run the setup notebooks to generate the required data
2. Execute `06_Generate_Unstructured_Data.py` to create the vector index for unstructured data
3. Customize the Genie integration in `07_More_Functions.py`:
   - Update the Databricks host URL and token
   - Specify your Genie Space ID
4. Use the SQL functions to query the agent:
   ```sql
   SELECT ask_genie_pharma_gsc(
     'What raw materials are in short supply?',
     'no relevant history'
   );
   ```
5. For unstructured data queries:
   ```sql
   SELECT query_unstructured_emails(
     'What delivery delays are affecting Distribution Center 3?'
   );
   ```

## Key Features

- **Scalable Forecasting**: Distributed forecasting for thousands of product/location combinations
- **Graph-Based BOM Analysis**: Efficiently derive raw material needs from product forecasts
- **Optimization at Scale**: Linear programming to optimize transportation network
- **Configurable Parameters**: Easily adjust number of plants, distribution centers, and products

## Data Model

The solution uses the following key tables:
- `product_demand_historical`: Historical product demand by wholesaler
- `product_demand_forecasted`: Forecasted product demand by distribution center
- `distribution_center_to_wholesaler_mapping`: Mapping between distribution centers and wholesalers
- `bom`: Bill of materials with material relationships
- `raw_material_demand`: Calculated raw material requirements
- `plant_supply`: Maximum supply capacity by plant and product
- `transport_cost`: Transportation costs between plants and distribution centers


## Acknowledgments

This project is based on Databricks' supply chain optimization solution accelerator available at: https://github.com/databricks-industry-solutions/supply-chain-optimization