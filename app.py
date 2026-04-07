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

# ENGINE WITH AUTO MODEL FALLBACK
class InvestSmartEngine:
    def __init__(self, api_key, pdf_chunks):
        genai.configure(api_key=api_key)
        self.pdf_chunks = pdf_chunks
        self.available_models = self.get_compatible_models()
        self.model_index = 0
        self.model = self.init_model(self.model_index)

    def get_compatible_models(self):
        """Return a list of all models supporting generateContent."""
        try:
            models = genai.list_models()
            compatible = [m["name"] for m in models if "generateContent" in m.get("capabilities", [])]
            if not compatible:
                st.sidebar.error("No compatible models found that support generateContent.")
            else:
                st.sidebar.info(f"Found {len(compatible)} compatible model(s).")
            return compatible
        except Exception as e:
            st.sidebar.error(f"Error fetching models: {e}")
            return []

    def init_model(self, index):
        """Initialize the model by index."""
        if self.available_models and 0 <= index < len(self.available_models):
            st.sidebar.info(f"✅ Using model: {self.available_models[index]}")
            return genai.GenerativeModel(model_name=self

