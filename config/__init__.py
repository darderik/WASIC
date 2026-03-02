from .config import Config
import os 
from pathlib import Path

# Create data and data backups
data_charts_path = Path(Config().get("data_charts_path"))
bkp_rel_path = Config().get("data_charts_relative_bkps")

# Create data charts path folder
data_charts_path.mkdir(parents=True, exist_ok=True)

# Create data backups folder
backup_path = data_charts_path / bkp_rel_path
backup_path.mkdir(parents=True, exist_ok=True)