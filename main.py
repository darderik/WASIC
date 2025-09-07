import os
from charset_normalizer import detect
from streamlit import connection
import streamlit.web.bootstrap
import logging
from config import Config
from connections.utilities import detect_baud_rate
from tasks import Tasks
from connections import Connections

# Import for forcing initialization of tasks
from addons.tasks import *
import threading
from wasic_test import test_function


def main():
    # Create the directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    # Setup handlers (robust, always works)
    import logging
    log_path = os.path.join("data", "wasic.log")
    file_handler = logging.FileHandler(log_path, mode="w")
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    # Defensive: ensure log level is always valid
    log_level = Config().get("log_level", "INFO") or "INFO"
    root_logger.setLevel(log_level)
    # Remove all handlers associated with the root logger object.
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    logging.info("Starting WASIC...")

    # Streamlit boot
    script_path = os.path.abspath("streamlit_app.py")
    # New thread test function
    # Create and start a new thread to run test_function
    #    test_thread.start()
    #detect_baud_rate("COM10")
    Connections().fetch_all_instruments()
    
    
    Tasks().run_task("Anisotropy Meas SM2401+34420+2RM")
    streamlit.web.bootstrap.run(script_path, False, [], {})

if __name__ == "__main__":
    main()
