import streamlit as st
import google.generativeai as genai
import os
import hashlib
import hmac
import json
import re
import datetime
import uuid
from pypdf import PdfReader

# CONFIG
st.set_page_config(page_title="InvestSmart AI (Ent. Edition)", page_icon="🛡️", layout="wide")

# CHUNKING
def chunk_text(text, chunk_size=500):
    words = text.split()
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]

# SECURITY LAYER
class SecurityLayer:
    @staticmethod
    def get_or_create_salt():
        if "user_salt" not in st.session_state:
            st.session_state.user_salt = str(uuid.uuid4())
        return st.session_state.user_salt

    @staticmethod
    def crypto_shred():
        st.session_state.clear()
        st.toast("⚠️ Session wiped.")

    @staticmethod
    def log_interaction(prompt, role):
        salt = SecurityLayer.get_or_create_salt()
        timestamp = datetime.datetime.now().isoformat()
        message = f"{prompt}{salt}{timestamp}"
        secure_hash = hmac.new(
            key=salt.encode(),
            msg=message.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()

        entry = {
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "role": role,
            "hash": secure_hash[:12]
        }

        if "audit_log" not in st.session_state:
            st.session_state.audit_log = []
        st.session_state.audit_log.append(entry)

# COST MONITOR
class CostMonitor:
    @staticmethod
    def estimate_cost(char_count):
        rate = 0.00001875
        cost = (char_count / 1000) * rate
        if "total_cost" not in st.session_state:
            st.session_state.total_cost = 0.0
        st.session_state.total_cost += cost

# PDF INGESTION
def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        content = page.extract_text()
        if content:
            text += content + "\n"
    return text

# ENGINE
class InvestSmartEngine:
    def __init__(self, api_key, pdf_chunks):
        genai.configure(api_key=api_key)
        self.pdf_chunks = pdf_chunks
        # STABLE MODEL PATH UPDATED BELOW
        self.model = genai.GenerativeModel(model_name='models/gemini-1.5-flash')

    def retrieve_context(self, query):
        for chunk in self.pdf_chunks:
            if any(word.lower() in chunk.lower() for word in query.split()):
                return chunk
        return self.pdf_chunks[0] if self.pdf_chunks else "No context available."

    def generate_response(self, user_query):
        try:
            context = self.retrieve_context(user_query)
            prompt = f"You are Aris, an AI policy assistant. Answer ONLY using this context: {context}\n\nQuestion: {user_query}"
            response = self.model.generate_content(prompt)
            CostMonitor.estimate_cost(len(prompt))
            SecurityLayer.log_interaction(user_query, "user")
            return response.text
        except Exception as e:
            return f"❌ Error connecting to Gemini: {str(e)}"

# MAIN APP
def main():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "total_cost" not in st.session_state:
        st.session_state.total_cost = 0.0

    st.sidebar.title("Admin")
    
    # Check if API Key is in secrets first
    api_key = None
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.sidebar.success("✅ API Key active from Secrets")
    else:
        api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")
        if not api_key:
            st.warning("Please add your API Key to Streamlit Secrets or enter it here.")

    uploaded_file = st.sidebar.file_uploader("Upload PDF", type="pdf")

    if uploaded_file:
        text = extract_text_from_pdf(uploaded_file)
        chunks = chunk_text(text)
    else:
        text = "Sample policy: Uber not covered. Grace period 30 days."
        chunks = chunk_text(text)

    if api_key:
        engine = InvestSmartEngine(api_key, chunks)

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Ask Aris..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                reply = engine.generate_response(prompt)
                st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})

    st.sidebar.metric("Cost", f"${st.session_state.total_cost:.6f}")

    if "audit_log" in st.session_state:
        with st.sidebar.expander("Audit Log"):
            st.write(st.session_state.audit_log)

if __name__ == "__main__":
    main()

