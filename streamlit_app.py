
import streamlit as st

st.set_page_config(page_title="FIS-Alpine-Athlete-Analysis", layout="wide")

st.title("⛷️ FIS-Alpine-Athlete-Analysis")

st.write(
"""Search and explore alpine ski athletes from the FIS database.
Enter a **name** or **FIS code** to find the athlete profile."""
)

query = st.text_input("Search athlete")

if query:
    st.success(f"Search feature placeholder for: {query}")
    st.write("Connect your scraping / data logic here.")
