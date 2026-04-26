import streamlit as st
import google.generativeai as genai
import hashlib
import hmac
import datetime
import uuid
import re
import math
from pypdf import PdfReader


st.set_page_config(page_title="InvestSmart AI (Ent. Edition)", page_icon="🛡️", layout="wide")


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


def chunk_text(text, chunk_size=500):
    words = text.split()
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]


class BM25Retriever:
    def __init__(self, documents):
        self.documents = documents
        self.tokenized_docs = [self.tokenize(doc) for doc in documents]
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        self.avgdl = 0
        self.initialize()

    def tokenize(self, text):
        return re.findall(r'\w+', text.lower())

    def initialize(self):
        N = len(self.tokenized_docs)
        df = {}

        for doc in self.tokenized_docs:
            self.doc_len.append(len(doc))
            freqs = {}
            for w in doc:
                freqs[w] = freqs.get(w, 0) + 1
            self.doc_freqs.append(freqs)

            for w in freqs:
                df[w] = df.get(w, 0) + 1

        self.avgdl = sum(self.doc_len) / max(len(self.doc_len), 1)

        for w, f in df.items():
            self.idf[w] = math.log((N - f + 0.5) / (f + 0.5) + 1)

    def score(self, query_tokens, index):
        score = 0.0
        doc = self.doc_freqs[index]

        for q in query_tokens:
            if q in doc:
                f = doc[q]
                score += self.idf.get(q, 0) * ((f * 1.5) / (f + 0.5))

        return score

    def retrieve(self, query, top_k=3):
        query_tokens = self.tokenize(query)

        scored = []
        for i in range(len(self.documents)):
            scored.append((self.score(query_tokens, i), self.documents[i]))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = [doc for score, doc in scored[:top_k] if score > 0]

        return results if results else [self.documents[0]]


class SecurityLayer:
    @staticmethod
    def get_or_create_salt():
        if "user_salt" not in st.session_state:
            st.session_state.user_salt = str(uuid.uuid4())
        return st.session_state.user_salt

    @staticmethod
    def crypto_shred():
        st.session_state.clear()
        st.toast("Session wiped")

    @staticmethod
    def log_interaction(prompt, role):
        salt = SecurityLayer.get_or_create_salt()
        timestamp = datetime.datetime.now().isoformat()

        msg = f"{prompt}{salt}{timestamp}"
        secure_hash = hmac.new(
            salt.encode(),
            msg.encode(),
            hashlib.sha256
        ).hexdigest()

        entry = {
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "role": role,
            "hash": secure_hash[:12]
        }

        if "audit_log" not in st.session_state:
            st.session_state.audit_log = []

        st.session_state.audit_log.append(entry)


class CostMonitor:
    @staticmethod
    def estimate_cost(char_count):
        rate = 0.00001875
        cost = (char_count / 1000) * rate

        if "total_cost" not in st.session_state:
            st.session_state.total_cost = 0.0

        st.session_state.total_cost += cost


def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""

    for page in reader.pages:
        content = page.extract_text()
        if content:
            text += content + "\n"

    return text


class InvestSmartEngine:
    def __init__(self, api_key, pdf_chunks):
        genai.configure(api_key=api_key)
        self.pdf_chunks = pdf_chunks
        self.retriever = BM25Retriever(pdf_chunks)

        self.models = self.get_models()
        self.model_index = 0
        self.model = self.init_model(0)

    def get_models(self):
        try:
            models = genai.list_models()
            return [
                m.name for m in models
                if "generateContent" in m.supported_generation_methods
            ] or ["models/gemini-1.5-flash"]
        except:
            return ["models/gemini-1.5-flash"]

    def init_model(self, i):
        try:
            name = self.models[i]
            st.sidebar.info(f"Active Model: {name}")
            return genai.GenerativeModel(model_name=name)
        except:
            return None

    def retrieve_context(self, query):
        chunks = self.retriever.retrieve(query, top_k=3)
        return "\n\n".join(chunks)

    def generate_response(self, query):
        for _ in range(len(self.models)):
            try:
                if not self.model:
                    self.model = self.init_model(self.model_index)

                context = self.retrieve_context(query)

                prompt = (
                    "You are Aris, an investment policy expert for InvestSmart AI. "
                    "Answer ONLY using the provided context.\n\n"
                    f"CONTEXT:\n{context}\n\n"
                    f"QUESTION:\n{query}"
                )

                response = self.model.generate_content(prompt)
                text = response.text if hasattr(response, "text") else "No response"

                CostMonitor.estimate_cost(len(prompt))
                SecurityLayer.log_interaction(query, "user")

                return text

            except:
                self.model_index = (self.model_index + 1) % len(self.models)
                self.model = self.init_model(self.model_index)

        return "Model error"


def main():
    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.title("InvestSmart AI")

    api_key = st.sidebar.text_input("API Key", type="password")
    uploaded = st.sidebar.file_uploader("Upload PDF", type="pdf")

    if uploaded:
        if "chunks" not in st.session_state:
            text = extract_text_from_pdf(uploaded)
            st.session_state.chunks = chunk_text(text)

        chunks = st.session_state.chunks
    else:
        chunks = chunk_text("Sample policy: 12% return, 6-month lock-in")

    if api_key:
        engine = InvestSmartEngine(api_key, chunks)

        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

        if q := st.chat_input("Ask..."):
            st.session_state.messages.append({"role": "user", "content": q})

            with st.chat_message("user"):
                st.markdown(q)

            with st.chat_message("assistant"):
                r = engine.generate_response(q)
                st.markdown(r)

            st.session_state.messages.append({"role": "assistant", "content": r})


if __name__ == "__main__":
    main()
