import streamlit as st
from workflow import create_workflow, run_query

st.set_page_config(
    page_title="Multi-Agent Support System",
    page_icon="🤖",
    layout="centered"
)

st.title("🤖 Multi-Agent Support System")
st.caption("Supervisor → IT / Finance routing using LangGraph")

@st.cache_resource
def load_workflow():
    return create_workflow()

workflow = load_workflow()


if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


for role, message in st.session_state.chat_history:
    with st.chat_message(role):
        st.markdown(message)

user_query = st.chat_input("Ask an IT or Finance question...")

if user_query:
    # Show user message
    st.session_state.chat_history.append(("user", user_query))
    with st.chat_message("user"):
        st.markdown(user_query)

    # Run workflow
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = run_query(workflow, user_query)
            except Exception as e:
                response = f"❌ Error: {str(e)}"

        st.markdown(response)

    st.session_state.chat_history.append(("assistant", response))


with st.sidebar:
    st.header("ℹ️ System Info")
    st.markdown("""
    **Agents**
    - 🧠 Supervisor Agent
    - 💻 IT Support Agent
    - 💰 Finance Agent

    **Routing**
    - Supervisor classifies the query
    - Routes to the appropriate agent
    """)

    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []
        st.rerun()
