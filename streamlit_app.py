import streamlit

pg = streamlit.navigation([streamlit.Page("./webapp/pages/home.py"), streamlit.Page("./webapp/pages/instr_1.py")])
pg.run()
