import streamlit as st
from connections import Connections
from typing import List, Optional
from streamlit.navigation.page import StreamlitPage
from instruments.properties import property_info

page_array = [
    st.Page(page="./webapp/pages/home.py", title="Home"),
    st.Page(page="./webapp/pages/instruments.py", title="Instruments"),
    st.Page(page="./webapp/pages/tasks.py", title="Tasks"),
    st.Page(page="./webapp/pages/charts.py", title="Charts"),
]
st.set_page_config(page_title="WASIC", page_icon="🔌", layout="wide")
pg = st.navigation(page_array)
pg.run()
