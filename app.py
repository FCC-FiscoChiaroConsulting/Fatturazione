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

# Dati emittente (modificali con i tuoi reali)
EMITTENTE = {
    "Denominazione": "FISCO CHIARO CONSULTING",
    "Indirizzo": "Via / Piazza ....",
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

# Per gestire lo switch "Nuovo cliente"
if "forza_nuovo_cliente" not in st.session_state:
    st.session_state.forza_nuovo_cliente = False


# ==========================
# FUNZIONI PDF
# ==========================

def _format_val_eur(val: float) -> str:
    return (
        f"{val:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def genera_pdf_fattura(
    numero: str,
    data_f: date,
    cliente: dict,
    righe: list,
    imponibile: float,
    iva: float,
    totale: float,
) -> bytes:
    """
    Genera PDF della fattura con layout tipo copia di cortesia SdI.
    """
    pdf = FPDF()
    pdf.add_page()

    # ---------- HEADER: EMITTENTE / CLIENTE ----------
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(10, 10)
    pdf.cell(0, 6, EMITTENTE["Denominazione"], ln=1)

    pdf.set_font("Helvetica", "", 9)
    em_ind = EMITTENTE.get("Indirizzo", "")
    pdf.set_x(10)
    pdf.cell(0, 4, em_ind, ln=1)

    em_line2_parts = []
    if EMITTENTE.get("CAP"):
        em_line2_parts.append(EMITTENTE["CAP"])
    if EMITTENTE.get("Comune"):
        em_line2_parts.append(EMITTENTE["Comune"])
    if EMITTENTE.get("Provincia"):
        em_line2_parts.append(f"({EMITTENTE['Provincia']})")
    em_line2 = " ".join(em_line2_parts)
    if em_line2:
        em_line2 += " IT"

    if em_line2:
        pdf.set_x(10)
        pdf.cell(0, 4, em_line2, ln=1)

    if EMITTENTE.get("CF"):
        pdf.set_x(10)
        pdf.cell(0, 4, f"CODICE FISCALE {EMITTENTE['CF']}", ln=1)
    if EMITTENTE.get("PIVA"):
        pdf.set_x(10)
        pdf.cell(0, 4, f"PARTITA IVA {EMITTENTE['PIVA']}", ln=1)

    # Cliente (a destra)
    den_cli = cliente.get("Denominazione", "-")
    ind_cli = cliente.get("Indirizzo", "")
    cap_cli = cliente.get("CAP", "")
    com_cli = cliente.get("Comune", "")
    prov_cli = cliente.get("Provincia", "")
    piva_cli = cliente.get("PIVA", "")

    cli_line2_parts = []
    if cap_cli:
        cli_line2_parts.append(cap_cli)
    if com_cli:
        cli_line2_parts.append(com_cli)
    if prov_cli:
        cli_line2_parts.append(f"({prov_cli})")
    cli_line2 = " ".join(cli_line2_parts)
    if cli_line2:
        cli_line2 += " IT"

    pdf.set_xy(120, 10)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 4, "Spett.le", ln=1)

    pdf.set_x(120)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 5, den_cli, ln=1)

    pdf.set_font("Helvetica", "", 9)
    if ind_cli:
        pdf.set_x(120)
        pdf.cell(0, 4, ind_cli, ln=1)
    if cli_line2:
        pdf.set_x(120)
        pdf.cell(0, 4, cli_line2, ln=1)
    if piva_cli:
        pdf.set_x(120)
        pdf.cell(0, 4, f"PARTITA IVA {piva_cli}", ln=1)

    pdf.ln(5)

    # ---------- DATI DOCUMENTO / TRASMISSIONE ----------
    pdf.set_fill_color(31, 119, 180)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)

    pdf.set_x(10)
    pdf.cell(95, 7, "DATI DOCUMENTO", border=1, ln=0, fill=True)
    pdf.cell(95, 7, "DATI TRASMISSIONE", border=1, ln=1, fill=True)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)

    # colonna sinistra
    pdf.set_x(10)
    pdf.cell(25, 6, "TIPO", border=1)
    pdf.cell(70, 6, "TD01 FATTURA - B2B", border=1, ln=1)

    pdf.set_x(10)
    pdf.cell(25, 6, "NUMERO", border=1)
    pdf.cell(70, 6, str(numero), border=1, ln=1)

    pdf.set_x(10)
    pdf.cell(25, 6, "DATA", border=1)
    pdf.cell(70, 6, data_f.strftime("%d/%m/%Y"), border=1, ln=1)

    # CAUSALE: uso la prima descrizione accorciata, se presente
    causale = ""
    if righe:
        causale = (righe[0].get("desc") or "").replace("\n", " ").strip()
        if len(causale) > 40:
            causale = causale[:37] + "..."
    if not causale:
        causale = "SERVIZIO"

    pdf.set_x(10)
    pdf.cell(25, 6, "CAUSALE", border=1)
    pdf.cell(70, 6, causale, border=1, ln=1)

    # colonna destra (placeholder)
    pdf.set_xy(105, pdf.get_y() - 24)  # risalgo di 4 righe
    pdf.cell(35, 6, "CODICE DESTINATARIO", border=1)
    pdf.cell(60, 6, "0000000", border=1, ln=1)

    pdf.set_x(105)
    pdf.cell(35, 6, "PEC DESTINATARIO", border=1)
    pdf.cell(60, 6, "", border=1, ln=1)

    pdf.set_x(105)
    pdf.cell(35, 6, "DATA INVIO", border=1)
    pdf.cell(60, 6, "", border=1, ln=1)

    pdf.set_x(105)
    pdf.cell(35, 6, "IDENTIFICATIVO SDI", border=1)
    pdf.cell(60, 6, "", border=1, ln=1)

    pdf.ln(4)

    # ---------- DETTAGLIO DOCUMENTO ----------
    pdf.set_fill_color(31, 119, 180)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_x(10)
    pdf.cell(190, 7, "DETTAGLIO DOCUMENTO", border=1,
