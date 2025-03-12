import os
import streamlit.web.bootstrap
import logging
from config import Config

# Import for forcing initialization of tasks
from user_defined.tasks import *


def main():

    # Logger init
    logging.basicConfig(
        level=Config().get("log_level", "NOTSET"),
        filename=os.path.join("data", "wasic.log"),
        filemode="w",
    )
    # Override disable logger
    logging.disable()

    # Streamlit boot
    script_path = os.path.abspath("streamlit_app.py")
    logging.basicConfig(level="INFO")
    streamlit.web.bootstrap.run(script_path, False, [], {})


if __name__ == "__main__":
    main()
