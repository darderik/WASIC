import streamlit as st
from typing import List, Optional
import time
from streamlit.delta_generator import DeltaGenerator
from dataclasses import dataclass
from connections import Connections
from instruments.properties import property_info
from easy_scpi import Instrument
from instruments import RaspberrySIM
from tasks import Task, Tasks

st.title("Tasks selector")
isTaskRunning: bool = Tasks._is_running is not None

task_selectbox: str = st.selectbox(
    "Select Task",
    [cur.name for cur in Tasks.tasks_list],
    disabled=isTaskRunning,
)
st.button(
    "Run Task",
    on_click=Tasks.run_task,
    args=(task_selectbox,),
    disabled=isTaskRunning,
)

if isTaskRunning:
    st.button("Stop Task", on_click=Tasks.kill_task)
    curTask: Task = Tasks._is_running
    st.title(curTask.name)
    st.write(curTask.description)
    st.write("Instruments:")
    for cur in curTask.instruments:
        st.write(cur.scpi_instrument.id)
    st.write("Data:")
    scatter_plot: DeltaGenerator = st.scatter_chart()
    while True:
        time.sleep(1)
        scatter_plot.line_chart(curTask.data["x"])
