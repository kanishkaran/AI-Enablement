import streamlit as st
import boto3


from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Web Scraper Agent",
    page_icon="🤖",
    layout="wide"
)

# Title
st.title("Web Scraper Agent")
st.markdown("Interact with the Bedrock Agent to scrape websites")

# Sidebar for AWS configuration
st.sidebar.header("Configuration")

# AWS credentials and region
aws_region = st.sidebar.text_input("AWS Region", value="us-east-1")
agent_id = st.sidebar.text_input("Agent ID", placeholder="Enter your Bedrock Agent ID")
agent_alias_id = st.sidebar.text_input("Agent Alias ID", value="TSTALIASID", placeholder="Enter Agent Alias ID")

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'session_id' not in st.session_state:
    st.session_state.session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

# Function to invoke Bedrock Agent
def invoke_agent(prompt, agent_id, agent_alias_id, session_id, region):
    """Invoke the Bedrock Agent with a prompt"""
    try:
        # Create Bedrock Agent Runtime client
        client = boto3.client(
            'bedrock-agent-runtime',
            region_name=region
        )
        
        # Invoke the agent
        response = client.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=session_id,
            inputText=prompt
        )
        
        # Process the response stream
        result_text = ""
        for event in response['completion']:
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    result_text += chunk['bytes'].decode('utf-8')
        
        return result_text, None
        
    except Exception as e:
        print(f"Error occured while agent invoke: {e}")
        return None, str(e)

# Main chat interface
st.subheader("💬 Chat Interface")

# Display chat history
for message in st.session_state.chat_history:
    if message['role'] == 'user':
        st.markdown(f"**You:** {message['content']}")
    else:
        st.markdown(f"**Agent:** {message['content']}")
    st.markdown("---")

# Input area
col1, col2 = st.columns([5, 1])

with col1:
    user_input = st.text_input(
        "Enter your request",
        placeholder="e.g., Scrape https://example.com and summarize the content",
        key="user_input"
    )

with col2:
    send_button = st.button("Send", type="primary", use_container_width=True)

# Clear chat button
if st.sidebar.button("Clear Chat"):
    st.session_state.chat_history = []
    st.session_state.session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    st.rerun()

# Process input
if send_button and user_input:
    if not agent_id or not agent_alias_id:
        st.error("Please enter Agent ID and Agent Alias ID in the sidebar")
    else:
        # Add user message to chat history
        st.session_state.chat_history.append({
            'role': 'user',
            'content': user_input,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # Show loading spinner
        with st.spinner("Agent is processing your request..."):
            # Invoke the agent
            response_text, error = invoke_agent(
                user_input,
                agent_id,
                agent_alias_id,
                st.session_state.session_id,
                aws_region
            )
        
        if error:
            st.error(f"Error: {error}")
        else:
            # Add agent response to chat history
            st.session_state.chat_history.append({
                'role': 'agent',
                'content': response_text,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Rerun to update the chat display
        st.rerun()

# Sidebar information
st.sidebar.markdown("---")
st.sidebar.subheader("Session Info")
st.sidebar.text(f"Session ID: {st.session_state.session_id}")
st.sidebar.text(f"Messages: {len(st.session_state.chat_history)}")

# Instructions
st.sidebar.markdown("---")
st.sidebar.subheader("How to Use")
st.sidebar.markdown("""
1. Enter your AWS credentials
2. Provide your Agent ID and Alias ID
3. Type your request in the chat
4. Examples:
   - "Scrape https://bbc.com"
   - "Get the content from https://example.com"
   - "Scrape https://news.ycombinator.com and summarize"
""")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("Powered by Amazon Bedrock Agents")