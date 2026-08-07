# ui.py
#
# IMPORTANT: Before starting this app, deploy the Modal function by running:
#   modal deploy modal_test.py
# in your terminal. The function must be deployed before it can be looked up here.

import streamlit as st
import modal
from modal.exception import NotFoundError

# Import our database module (initializes tables automatically)
from db import (
    create_chat,
    get_all_chats,
    get_chat,
    rename_chat,
    delete_chat,
    update_chat_timestamp,
    add_message,
    get_messages,
    generate_chat_markdown,
    get_safe_filename,
)

# ─── Page Config ───
st.set_page_config(
    page_title="GPT-1900 Chatbot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───
st.markdown(
    """
<style>
    /* Global dark theme overrides */
    .stApp {
        background-color: #0d1117;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #0d1117;
        border-right: 1px solid #30363d;
    }
    [data-testid="stSidebar"] .stMarkdown {
        color: #c9d1d9;
    }

    /* Chat list items */
    .chat-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 14px;
        border-radius: 8px;
        margin-bottom: 4px;
        cursor: pointer;
        transition: background-color 0.15s ease;
        border-left: 3px solid transparent;
    }
    .chat-item:hover {
        background-color: #161b22;
    }
    .chat-item.active {
        background-color: rgba(31, 111, 235, 0.08);
        border-left: 3px solid #58a6ff;
    }
    .chat-item-left {
        flex: 1;
        min-width: 0;
    }
    .chat-title {
        font-size: 14px;
        font-weight: 500;
        color: #c9d1d9;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .chat-meta {
        font-size: 11px;
        color: #6e7681;
        margin-top: 2px;
    }
    .chat-actions {
        display: flex;
        gap: 4px;
        opacity: 0;
        transition: opacity 0.15s ease;
    }
    .chat-item:hover .chat-actions,
    .chat-item.active .chat-actions {
        opacity: 1;
    }
    .action-btn {
        background: transparent;
        border: none;
        color: #8b949e;
        cursor: pointer;
        padding: 4px 6px;
        border-radius: 4px;
        font-size: 13px;
        line-height: 1;
        transition: all 0.15s ease;
    }
    .action-btn:hover {
        background-color: #30363d;
        color: #c9d1d9;
    }

    /* Rename inline input */
    .rename-input {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 10px;
    }
    .rename-input input {
        flex: 1;
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 4px;
        color: #c9d1d9;
        padding: 4px 8px;
        font-size: 13px;
    }
    .rename-input input:focus {
        outline: none;
        border-color: #58a6ff;
    }

    /* Delete confirmation */
    .delete-confirm {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 10px;
        font-size: 12px;
    }
    .delete-confirm span {
        color: #f85149;
        flex: 1;
    }

    /* Messages */
    .message-container {
        margin-bottom: 16px;
        animation: fadeIn 0.3s ease;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .message-user {
        background-color: rgba(31, 111, 235, 0.1);
        border: 1px solid rgba(31, 111, 235, 0.2);
        border-radius: 12px;
        padding: 16px 20px;
    }
    .message-assistant {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 16px 20px;
    }
    .message-label {
        font-size: 12px;
        font-weight: 600;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .message-label-user {
        color: #58a6ff;
    }
    .message-label-assistant {
        color: #3fb950;
    }
    .message-time {
        font-size: 11px;
        color: #6e7681;
        margin-left: 8px;
        font-weight: 400;
        text-transform: none;
    }
    .message-content {
        font-size: 15px;
        line-height: 1.65;
        color: #c9d1d9;
    }
    .message-content pre {
        background-color: #0d1117;
        border-radius: 6px;
        padding: 12px;
        overflow-x: auto;
    }
    .message-content code {
        background-color: #0d1117;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 13px;
    }

    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 60px 20px;
        color: #8b949e;
    }
    .empty-state-icon {
        font-size: 48px;
        margin-bottom: 16px;
    }
    .empty-state h3 {
        color: #c9d1d9;
        font-size: 18px;
        font-weight: 500;
        margin-bottom: 8px;
    }
    .empty-state p {
        font-size: 14px;
        color: #6e7681;
    }

    /* Example pills */
    .example-pill {
        display: inline-block;
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 20px;
        padding: 8px 16px;
        margin: 4px;
        font-size: 13px;
        color: #8b949e;
        cursor: pointer;
        transition: all 0.15s ease;
    }
    .example-pill:hover {
        border-color: #58a6ff;
        color: #58a6ff;
    }

    /* Input area */
    .input-area {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 16px;
    }
    .input-hint {
        font-size: 11px;
        color: #6e7681;
        margin-top: 6px;
    }

    /* Section headers in sidebar */
    .sidebar-section {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #8b949e;
        margin: 16px 0 8px 0;
        padding-left: 4px;
    }

    /* New chat button */
    .new-chat-btn {
        width: 100%;
        background-color: #1f6feb;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 10px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: background-color 0.15s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
    }
    .new-chat-btn:hover {
        background-color: #388bfd;
    }

    /* Scrollbar styling */
    ::-webkit-scrollbar {
        width: 6px;
    }
    ::-webkit-scrollbar-track {
        background: transparent;
    }
    ::-webkit-scrollbar-thumb {
        background: #30363d;
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #484f58;
    }

    /* Hide Streamlit default elements we don't want */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Download button styling in chat items */
    .stDownloadButton {
        display: inline-block;
    }
    .stDownloadButton button {
        background: transparent !important;
        border: none !important;
        color: #8b949e !important;
        padding: 4px 6px !important;
        font-size: 13px !important;
        min-height: unset !important;
        line-height: 1 !important;
    }
    .stDownloadButton button:hover {
        background-color: #30363d !important;
        color: #c9d1d9 !important;
    }
    .stDownloadButton button p {
        font-size: 13px !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ─── Session State Initialization ───
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None
if "editing_chat_id" not in st.session_state:
    st.session_state.editing_chat_id = None
if "edit_title_value" not in st.session_state:
    st.session_state.edit_title_value = ""
if "deleting_chat_id" not in st.session_state:
    st.session_state.deleting_chat_id = None
if "prompt_input" not in st.session_state:
    st.session_state.prompt_input = ""


# ─── Helper Functions ───

def select_chat(chat_id):
    """Switch to a different chat."""
    st.session_state.current_chat_id = chat_id
    st.session_state.editing_chat_id = None
    st.session_state.deleting_chat_id = None
    st.session_state.prompt_input = ""
    st.rerun()


def start_new_chat():
    """Create a new chat and select it."""
    chat_id = create_chat("New Chat")
    st.session_state.current_chat_id = chat_id
    st.session_state.editing_chat_id = None
    st.session_state.deleting_chat_id = None
    st.session_state.prompt_input = ""
    st.rerun()


def start_rename(chat_id, current_title):
    """Enter rename mode for a chat."""
    st.session_state.editing_chat_id = chat_id
    st.session_state.edit_title_value = current_title
    st.session_state.deleting_chat_id = None
    st.rerun()


def confirm_rename(chat_id):
    """Save the rename."""
    new_title = st.session_state.edit_title_value.strip()
    if new_title:
        rename_chat(chat_id, new_title)
    st.session_state.editing_chat_id = None
    st.session_state.edit_title_value = ""
    st.rerun()


def cancel_rename():
    """Cancel rename mode."""
    st.session_state.editing_chat_id = None
    st.session_state.edit_title_value = ""
    st.rerun()


def start_delete(chat_id):
    """Enter delete confirmation mode."""
    st.session_state.deleting_chat_id = chat_id
    st.session_state.editing_chat_id = None
    st.rerun()


def confirm_delete(chat_id):
    """Delete the chat and clear selection if it was active."""
    delete_chat(chat_id)
    if st.session_state.current_chat_id == chat_id:
        st.session_state.current_chat_id = None
    st.session_state.deleting_chat_id = None
    st.rerun()


def cancel_delete():
    """Cancel delete confirmation."""
    st.session_state.deleting_chat_id = None
    st.rerun()


# ─── Sidebar ───
with st.sidebar:
    # Header
    st.markdown("<h1 style='font-size:20px; font-weight:700; color:#f0f6fc; margin-bottom:2px;'>🤖 GPT-1900</h1>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:12px; color:#8b949e; margin-bottom:16px;'>Chat History</p>", unsafe_allow_html=True)

    # New Chat Button
    if st.button("➕  New Chat", key="new_chat_btn", use_container_width=True, type="primary"):
        start_new_chat()

    st.markdown("<div class='sidebar-section'>Conversations</div>", unsafe_allow_html=True)

    # Chat List
    chats = get_all_chats()

    if not chats:
        st.markdown(
            "<p style='font-size:13px; color:#6e7681; text-align:center; padding:20px 0;'>"
            "No chats yet.<br>Click \"New Chat\" to start."
            "</p>",
            unsafe_allow_html=True,
        )
    else:
        for chat in chats:
            chat_id = chat["id"]
            is_active = st.session_state.current_chat_id == chat_id
            is_editing = st.session_state.editing_chat_id == chat_id
            is_deleting = st.session_state.deleting_chat_id == chat_id

            # Build chat item HTML
            active_class = "active" if is_active else ""

            if is_editing:
                # Inline rename input
                col1, col2, col3 = st.columns([6, 1, 1])
                with col1:
                    new_name = st.text_input(
                        "Rename",
                        value=st.session_state.edit_title_value,
                        key=f"rename_input_{chat_id}",
                        label_visibility="collapsed",
                    )
                    st.session_state.edit_title_value = new_name
                with col2:
                    if st.button("✓", key=f"rename_confirm_{chat_id}", help="Save"):
                        confirm_rename(chat_id)
                with col3:
                    if st.button("✕", key=f"rename_cancel_{chat_id}", help="Cancel"):
                        cancel_rename()

            elif is_deleting:
                # Inline delete confirmation
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    st.markdown("<span style='color:#f85149; font-size:12px;'>Delete this chat?</span>", unsafe_allow_html=True)
                with col2:
                    if st.button("Yes", key=f"delete_confirm_{chat_id}", help="Confirm delete"):
                        confirm_delete(chat_id)
                with col3:
                    if st.button("No", key=f"delete_cancel_{chat_id}", help="Cancel"):
                        cancel_delete()

            else:
                # Normal chat item display
                # Use columns for layout: title area | action buttons
                col_main, col_actions = st.columns([5, 2])

                with col_main:
                    # Make the title area clickable to select the chat
                    st.markdown(
                        f"""
                        <div class="chat-item {active_class}" onclick="">
                            <div class="chat-item-left">
                                <div class="chat-title">{chat['title']}</div>
                                <div class="chat-meta">{chat['updated_at']}</div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    # Hidden button overlay for clicking the chat item
                    if st.button(
                        "Select",
                        key=f"select_{chat_id}",
                        use_container_width=True,
                        help=f"Open: {chat['title']}",
                    ):
                        select_chat(chat_id)

                with col_actions:
                    # Action buttons: rename, download, delete
                    a_col1, a_col2, a_col3 = st.columns(3)
                    with a_col1:
                        if st.button("✏️", key=f"act_rename_{chat_id}", help="Rename chat"):
                            start_rename(chat_id, chat["title"])
                    with a_col2:
                        # Download button for this chat
                        md_content = generate_chat_markdown(chat_id)
                        filename = get_safe_filename(chat["title"])
                        st.download_button(
                            label="⬇️",
                            data=md_content,
                            file_name=filename,
                            mime="text/markdown",
                            key=f"act_download_{chat_id}",
                            help="Download as Markdown",
                        )
                    with a_col3:
                        if st.button("🗑️", key=f"act_delete_{chat_id}", help="Delete chat"):
                            start_delete(chat_id)

    # Settings Section
    st.markdown("<div class='sidebar-section'>Settings</div>", unsafe_allow_html=True)
    temperature = st.slider("Temperature", 0.1, 2.0, 0.65, 0.05)

    st.divider()
    st.subheader("Model Info")
    st.info("GPT-1900 | 34 layers | A100 GPU")

    st.divider()
    st.subheader("Examples")
    examples = [
        "You are a Victorian scholar. How would you organize a library?",
        "As a 19th century mathematician, explain logarithms.",
        "Describe the future of transportation (1890s perspective).",
    ]
    for i, ex in enumerate(examples):
        if st.button(f"Example {i+1}", key=f"ex_{i}", use_container_width=True):
            st.session_state.prompt_input = ex
            st.rerun()


# ─── Main Content Area ───

# Chat title bar
if st.session_state.current_chat_id:
    current_chat = get_chat(st.session_state.current_chat_id)
    if current_chat:
        col_title, col_download = st.columns([6, 1])
        with col_title:
            st.markdown(
                f"""<h2 style='font-size:20px; font-weight:600; color:#f0f6fc; margin-bottom:4px;'>
                {current_chat['title']}
                </h2>""",
                unsafe_allow_html=True,
            )
        with col_download:
            md_content = generate_chat_markdown(st.session_state.current_chat_id)
            filename = get_safe_filename(current_chat["title"])
            st.download_button(
                label="⬇️ Download",
                data=md_content,
                file_name=filename,
                mime="text/markdown",
                key="main_download_btn",
                use_container_width=True,
            )
        st.markdown(
            f"""<p style='font-size:12px; color:#6e7681; margin-bottom:16px;'>
            Created: {current_chat['created_at']} | Updated: {current_chat['updated_at']}
            </p>""",
            unsafe_allow_html=True,
        )
else:
    st.markdown("<h2 style='font-size:20px; font-weight:600; color:#f0f6fc;'>GPT-1900 Chatbot</h2>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:13px; color:#8b949e; margin-bottom:16px;'>*A consulting scholar from 1899, running on Modal A100 GPU*</p>", unsafe_allow_html=True)

st.divider()

# ─── Messages Display ───

if st.session_state.current_chat_id:
    messages = get_messages(st.session_state.current_chat_id)

    if messages:
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            timestamp = msg["created_at"]

            if role == "user":
                st.markdown(
                    f"""
                    <div class="message-container">
                        <div class="message-user">
                            <div class="message-label message-label-user">
                                You <span class="message-time">{timestamp}</span>
                            </div>
                            <div class="message-content">{content}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div class="message-container">
                        <div class="message-assistant">
                            <div class="message-label message-label-assistant">
                                GPT-1900 <span class="message-time">{timestamp}</span>
                            </div>
                            <div class="message-content">{content}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                # Also show code block for copy-paste convenience
                with st.expander("Copy raw response", expanded=False):
                    st.code(content, language="text")
    else:
        # Empty chat state with example prompts
        st.markdown(
            """
            <div class="empty-state">
                <div class="empty-state-icon">💬</div>
                <h3>Start a new conversation</h3>
                <p>Type your prompt below to begin chatting with GPT-1900.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # Example pills
        cols = st.columns(3)
        example_prompts = [
            "Explain quantum mechanics like I'm 5",
            "Write a Victorian-era letter to a friend",
            "Solve this riddle: I speak without a mouth...",
        ]
        for i, prompt_text in enumerate(example_prompts):
            with cols[i]:
                if st.button(prompt_text, key=f"quick_ex_{i}", use_container_width=True):
                    st.session_state.prompt_input = prompt_text
                    st.rerun()
else:
    # No chat selected state
    st.markdown(
        """
        <div class="empty-state">
            <div class="empty-state-icon">🤖</div>
            <h3>Welcome to GPT-1900</h3>
            <p>Select a chat from the sidebar or click "New Chat" to begin.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ─── Input Area ───
st.divider()

# Only show input if a chat is selected
if st.session_state.current_chat_id:
    st.subheader("Enter Your Prompt")
    col1, col2 = st.columns([4, 1])

    with col1:
        prompt = st.text_area(
            "Prompt",
            value=st.session_state.prompt_input,
            height=120,
            label_visibility="collapsed",
            key="prompt_textarea",
            placeholder="Type your message here...",
        )
        st.session_state.prompt_input = prompt

    with col2:
        st.write("")
        st.write("")
        submit_button = st.button("Submit", type="primary", use_container_width=True)

    st.markdown(
        "<p class='input-hint'>Press Ctrl+Enter to send</p>",
        unsafe_allow_html=True,
    )

    # ─── Handle Submission ───
    if submit_button and prompt.strip():
        chat_id = st.session_state.current_chat_id

        # Save user message to database
        add_message(chat_id, "user", prompt.strip())
        update_chat_timestamp(chat_id)

        status = st.empty()

        try:
            status.text("Connecting to Modal and running inference...")

            # Look up the deployed Modal function
            run_prompt = modal.Function.from_name("gpt1900-test", "run_prompt")
            response = run_prompt.remote(prompt.strip())

            status.empty()

            if response and not response.startswith("ERROR"):
                # Save assistant response to database
                add_message(chat_id, "assistant", response)
                update_chat_timestamp(chat_id)

                # Clear input and refresh to show new messages
                st.session_state.prompt_input = ""
                st.rerun()

            else:
                st.error(f"Model returned an error: {response}")

        except NotFoundError:
            status.empty()
            st.error(
                "Modal function not found. Make sure you have run "
                "`modal deploy modal_test.py` before starting this app."
            )
        except Exception as e:
            status.empty()
            st.error(f"Error: {str(e)}")

    elif submit_button and not prompt.strip():
        st.warning("Please enter a prompt")

else:
    # No chat selected - prompt user to create one
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("➕  Create New Chat", type="primary", use_container_width=True):
            start_new_chat()

# ─── Footer ───
st.divider()
st.markdown(
    "<p style='font-size:11px; color:#484f58; text-align:center;'>"
    "Powered by Modal | GPT-1900 | Streamlit | SQLite Persistence"
    "</p>",
    unsafe_allow_html=True,
)