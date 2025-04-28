import os
import streamlit.web.bootstrap
import logging
from config import Config
from tasks import Tasks

# Import for forcing initialization of tasks
from user_defined.tasks import *


def main():
    # Create the directory if it doesn't exist
    os.makedirs("data", exist_ok=True)

    # Setup handlers
    file_handler = logging.FileHandler(os.path.join("data", "wasic.log"), mode="w")
    stream_handler = logging.StreamHandler()

    # Configure logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=Config().get("log_level", "NOTSET"),
        handlers=[file_handler, stream_handler],
    )
    logging.basicConfig(
        level=logging.DEBUG,
    )
    logging.info("Starting WASIC...")

    # Streamlit boot
    script_path = os.path.abspath("streamlit_app.py")
    logging.basicConfig(level="INFO")
    streamlit.web.bootstrap.run(script_path, False, [], {})


if __name__ == "__main__":
    main()
