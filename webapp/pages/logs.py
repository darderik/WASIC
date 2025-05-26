import streamlit as st
from pathlib import Path
import streamlit_scrollable_textbox as stx

# Title for the Logs page
st.title("📜 Live Logs Viewer")

# Path to the log file
log_file_path = Path("data\\wasic.log")
# Initialize session state for log content if not already present
if "log_content" not in st.session_state:
    st.session_state["log_content"] = ""


# Function to read the log file in a non-blocking way
def read_log_file(file_path: Path) -> str:
    try:
        with file_path.open("r", encoding="utf-8") as log_file:
            return log_file.read()
    except FileNotFoundError:
        return "Log file not found."
    except Exception as e:
        return f"Error reading log file: {e}"


# Fragment to update the log content periodically
@st.fragment(run_every=2)  # Refresh every 2 seconds
def update_log_buffer():
    st.session_state["log_content"] = read_log_file(log_file_path)
    stx.scrollableTextbox(
        text=st.session_state["log_content"],
        height=1000,
        key="log_display",
    )


with st.expander("📂 Live Log Contents", expanded=True):
    # Container for displaying logs
    with st.container():
        # Display the log file content
        update_log_buffer()
