import streamlit
from connections import Connections
from typing import List, Optional
from streamlit.navigation.page import StreamlitPage
from instruments.properties import property_info

page_array = [
    streamlit.Page(page="./webapp/pages/home.py", title="Home"),
    streamlit.Page(page="./webapp/pages/instruments.py", title="Instruments"),
    streamlit.Page(page="./webapp/pages/tasks.py", title="Tasks"),
]
pg = streamlit.navigation(page_array)
pg.run()

# streamlit.Page("./webapp/pages/instr_1.py")
