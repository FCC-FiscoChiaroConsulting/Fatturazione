import streamlit as st
import pandas as pd
from datetime import date
import os
from fpdf import FPDF
import base64

# ==========================
# CONFIGURAZIONE PAGINA
# ==========================
st.set_page_config(
    page_title="Fisco Chiaro Consulting - Fatturazione elettronica",
    layout="wide",
    page_icon="📄",
)

PRIMARY_BLUE = "#1f77b4"

PDF_DIR = "fatture_pdf"
os.makedirs(PDF_DIR, exist_ok=True)

# ====================================================
# DATI EMITTENTE (SOSTITUISCI CON I TUOI DATI REALI)
# ====================================================
EMITTENTE = {
    "Denominazione": "FISCO CHIARO CONSULTING",
    "Indirizzo": "Via/Piazza ... n. ...",
    "CAP": "00000",
    "Comune": "CITTÀ",
    "Provincia": "XX",
    "CF": "XXXXXXXXXXXX",
    "PIVA": "XXXXXXXXXXXX",
}

# ==========================
# STATO DI SESSIONE
# ==========================
COLONNE_DOC = [
    "Tipo",
    "Numero",
    "Data",
    "Controparte",
    "Importo",
    "Stato",
    "UUID",
    "PDF",
]

if "documenti_emessi" not in st.session_state:
    st.session_state.documenti_emessi = pd.DataFrame(columns=COLONNE_DOC)

if "clienti" not in st.session_state:
    st.session_state.clienti = pd.DataFrame(
        columns=[
            "Denominazione",
            "PIVA",
            "Indirizzo",
            "CAP",
            "Comune",
            "Provincia",
            "Tipo",  # Cliente/Fornitore
        ]
    )

if "righe_correnti" not in st.session_state:
    st.session_state.righe_correnti = []

if "forza_nuovo_cliente" not in st.session_state:
    st.session_state.forza_nuovo_cliente = False


# ==========================
# FUNZI
