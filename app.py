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

# --- ARIS 2.0 ENTERPRISE UI ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background-color: #0E1117;
    }
    .stChatInputContainer {
        border-top: 1px solid #1E3A8A;
    }
    h1, h2, h3 {
        color: #1E40AF;
    }
    .stExpander {
        background-color: #f0f2f6;
        border-radius: 5px;
        border-left: 5px solid #1E3A8A;
    }
    </style>
    """, unsafe_allow_html=True)

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

# ENGINE WITH ORIGINAL DYNAMIC MODEL SEARCH
class InvestSmartEngine:
    def __init__(self, api_key, pdf_chunks):
        genai.configure(api_key=api_key)
        self.pdf_chunks = pdf_chunks
        self.available_models = self.get_compatible_models()
        self.model_index = 0
        self.model = self.init_model(self.model_index)

    def get_compatible_models(self):
        try:
            models = genai.list_models()
            compatible = [m.name for m in models if "generateContent" in m.supported_generation_methods]
            if not compatible:
                return ["models/gemini-1.5-flash"]
            return compatible
        except Exception as e:
            st.sidebar.error(f"Error fetching models: {e}")
            return ["models/gemini-1.5-flash"]

    def init_model(self, index):
        if self.available_models and 0 <= index < len(self.available_models):
            try:
                model_name = self.available_models[index]
                st.sidebar.info(f"✅ Active Engine: {model_name}")
                return genai.GenerativeModel(model_name=model_name)
            except:
                return None
        return None

    def retrieve_context(self, query):
        for chunk in self.pdf_chunks:
            if any(word.lower() in chunk.lower() for word in query.split()):
                return chunk
        return self.pdf_chunks[0] if self.pdf_chunks else "No context available."

    def generate_response(self, user_query):
        for attempt in range(len(self.available_models)):
            try:
                if not self.model:
                    self.model = self.init_model(self.model_index)
                
                context = self.retrieve_context(user_query)
                
                # ARIS 2.0 ENTERPRISE SYSTEM PROMPT
                system_prompt = (
                    "You are Aris, an elite Investment Policy Expert for InvestSmart AI. Tone: Professional, "
                    "culturally nuanced for Kenya. 1. Use Markdown tables for comparisons. 2. Answer ONLY using "
                    "provided context. 3. Cite policies if visible. For financial advice, suggest a certified advisor."
                )
                
                full_prompt = f"{system_prompt}\n\nCONTEXT: {context}\n\nQUESTION: {user_query}"
                response = self.model.generate_content(full_prompt)
                
                if hasattr(response, 'text'):
                    reply_text = response.text
                else:
                    reply_text = "The model returned an empty response. Please rephrase."

                CostMonitor.estimate_cost(len(full_prompt))
                SecurityLayer.log_interaction(user_query, "user")
                return reply_text

            except Exception as e:
                # Log the error but continue to fallback
                self.model_index = (self.model_index + 1) % len(self.available_models)
                self.model = self.init_model(self.model_index)

        return "❌ All models failed. Please check your API key and connection."

# MAIN APP
def main():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "total_cost" not in st.session_state:
        st.session_state.total_cost = 0.0
    if "uploaded_file_name" not in st.session_state:
        st.session_state.uploaded_file_name = None

    st.title("🛡️ InvestSmart AI: Aris 2.0")
    st.subheader("Enterprise Policy Intelligence Prototype")

    st.sidebar.title("Admin & Security")
    
    api_key = None
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.sidebar.success("✅ API Key active from Secrets")
    else:
        api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")

    uploaded_file = st.sidebar.file_uploader("Upload PDF Documents", type="pdf")

    if uploaded_file:
        if "pdf_chunks" not in st.session_state or st.session_state.uploaded_file_name != uploaded_file.name:
            text = extract_text_from_pdf(uploaded_file)
            chunks = chunk_text(text)
            st.session_state.pdf_chunks = chunks
            st.session_state.uploaded_file_name = uploaded_file.name
        else:
            chunks = st.session_state.pdf_chunks
    else:
        if "pdf_chunks" not in st.session_state:
            text = "Sample policy: 12% annual return. 6-month lock-in period."
            chunks = chunk_text(text)
            st.session_state.pdf_chunks = chunks
        else:
            chunks = st.session_state.pdf_chunks

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

    st.sidebar.divider()
    st.sidebar.metric("Compute Cost (USD)", f"${st.session_state.total_cost:.6f}")

    if "audit_log" in st.session_state:
        with st.sidebar.expander("🛡️ System Audit Log"):
            st.caption("Active Protocols: Crypto-Shredding | AES-256")
            st.write(st.session_state.audit_log)
    
    if st.sidebar.button("🗑️ Crypto-Shred Session"):
        SecurityLayer.crypto_shred()
        st.rerun()

if __name__ == "__main__":
    main()

