from .config import Config
import os 

# Create data and data backups
data_charts_path = Config().get("data_charts_path")
bkp_rel_path = Config().get("data_charts_relative_bkps")

# Create data charts path folder
if not os.path.exists(data_charts_path):
    os.makedirs(data_charts_path)

# Create data backups folder
if not os.path.exists(f"{data_charts_path}\\"+bkp_rel_path):
    os.makedirs(f"{data_charts_path}\\"+bkp_rel_path)