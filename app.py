import streamlit as st
import pandas as pd
from datetime import date
import os
import re
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
    "Imponibile",
    "IVA",
    "Importo",     # totale a pagare
    "Stato",
    "UUID",
    "PDF",
]

CLIENTI_COLONNE = [
    "Denominazione",
    "PIVA",
    "CF",
    "Indirizzo",
    "CAP",
    "Comune",
    "Provincia",
    "CodiceDestinatario",
    "PEC",
    "Tipo",  # Cliente/Fornitore
]

# documenti emessi
if "documenti_emessi" not in st.session_state:
    st.session_state.documenti_emessi = pd.DataFrame(columns=COLONNE_DOC)
else:
    # garantisco tutte le colonne
    for col in COLONNE_DOC:
        if col not in st.session_state.documenti_emessi.columns:
            st.session_state.documenti_emessi[col] = 0 if col in ["Imponibile", "IVA", "Importo"] else ""

# rubrica clienti
if "clienti" not in st.session_state:
    st.session_state.clienti = pd.DataFrame(columns=CLIENTI_COLONNE)
else:
    for col in CLIENTI_COLONNE:
        if col not in st.session_state.clienti.columns:
            st.session_state.clienti[col] = ""

if "righe_correnti" not in st.session_state:
    st.session_state.righe_correnti = []

if "cliente_corrente_label" not in st.session_state:
    st.session_state.cliente_corrente_label = "NUOVO"

if "pagina_corrente" not in st.session_state:
    st.session_state.pagina_corrente = "Dashboard"


# ==========================
# FUNZIONI DI SUPPORTO
# ==========================
def _format_val_eur(val: float) -> str:
    """Formatta un numero in stile EUR italiano (senza simbolo €)."""
    return (
        f"{val:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def mostra_anteprima_pdf(pdf_bytes: bytes, altezza: int = 600):
    """Mostra un PDF inline come iframe tramite base64."""
    try:
        b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        pdf_display = f"""
        <iframe src="data:application/pdf;base64,{b64_pdf}"
                width="100%" height="{altezza}" type="application/pdf">
        </iframe>
        """
        st.markdown(pdf_display, unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"Impossibile mostrare l'anteprima PDF: {e}")


def get_next_invoice_number() -> str:
    """FT2025001, FT2025002, ... in base alle fatture dell'anno corrente."""
    year = date.today().year
    prefix = f"FT{year}"
    df = st.session_state.documenti_emessi
    seq = 1

    if not df.empty:
        mask = df["Numero"].astype(str).str.startswith(prefix)
        if mask.any():
            existing = df.loc[mask, "Numero"].astype(str)
            max_seq = 0
            for num in existing:
                m = re.search(rf"{prefix}(\d+)$", num)
                if m:
                    s = int(m.group(1))
                    if s > max_seq:
                        max_seq = s
            seq = max_seq + 1

    return f"{prefix}{seq:03d}"


def crea_riepilogo_fatture_emesse(df: pd.DataFrame):
    """Riepilogo per periodo: Importo a pagare / Imponibile / IVA."""
    if df.empty:
        st.info("Nessuna fattura emessa per creare il riepilogo.")
        return

    df = df.copy()
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")

    # selezione anno
    anni = sorted(df["Data"].dt.year.dropna().unique())
    if not anni:
        st.info("Nessuna data valida sulle fatture emesse.")
        return

    anno_default = date.today().year
    if anno_default not in anni:
        anno_default = anni[-1]

    idx_default = list(anni).index(anno_default)
    anno_sel = st.selectbox("Anno", anni, index=idx_default, key="anno_riepilogo_emesse")

    df_anno = df[df["Data"].dt.year == anno_sel]

    mesi_label = [
        "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
    ]

    rows = []

    # mesi
    for m in range(1, 13):
        df_m = df_anno[df_anno["Data"].dt.month == m]
        imp_tot = df_m["Importo"].sum()
        imp_imp = df_m["Imponibile"].sum()
        iva_tot = df_m["IVA"].sum()

        rows.append(
            {
                "Periodo": mesi_label[m - 1],
                "Importo a pagare": _format_val_eur(imp_tot),
                "Imponibile": _format_val_eur(imp_imp),
                "IVA": _format_val_eur(iva_tot),
            }
        )

    # trimestri
    trimestri = {
        "1° Trimestre": [1, 2, 3],
        "2° Trimestre": [4, 5, 6],
        "3° Trimestre": [7, 8, 9],
        "4° Trimestre": [10, 11, 12],
    }

    for nome, months in trimestri.items():
        df_q = df_anno[df_anno["Data"].dt.month.isin(months)]
        imp_tot = df_q["Importo"].sum()
        imp_imp = df_q["Imponibile"].sum()
        iva_tot = df_q["IVA"].sum()
        rows.append(
            {
                "Periodo": nome,
                "Importo a pagare": _format_val_eur(imp_tot),
                "Imponibile": _format_val_eur(imp_imp),
                "IVA": _format_val_eur(iva_tot),
            }
        )

    # annuale
    imp_tot = df_anno["Importo"].sum()
    imp_imp = df_anno["Imponibile"].sum()
    iva_tot = df_anno["IVA"].sum()
    rows.append(
        {
            "Periodo": "Annuale",
            "Importo a pagare": _format_val_eur(imp_tot),
            "Imponibile": _format_val_eur(imp_imp),
            "IVA": _format_val_eur(iva_tot),
        }
    )

    df_riep = pd.DataFrame(rows)

    st.markdown("### Prospetto riepilogativo fatture emesse")
    st.dataframe(
        df_riep,
        use_container_width=True,
        hide_index=True,
    )


# ==========================
# GENERAZIONE PDF FATTURA
# ==========================
def genera_pdf_fattura(
    numero: str,
    data_f: date,
    cliente: dict,
    righe: list,
    imponibile: float,
    iva: float,
    totale: float,
    modalita_pagamento: str = "",
    note: str = "",
) -> bytes:
    """PDF stile copia di cortesia SdI (senza carattere €)."""
    pdf = FPDF()
    pdf.add_page()

    # HEADER EMITTENTE
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(10, 10)
    pdf.cell(0, 6, EMITTENTE.get("Denominazione", ""), ln=1)

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

    # CLIENTE (DESTRA)
    den_cli = cliente.get("Denominazione", "-")
    ind_cli = cliente.get("Indirizzo", "")
    cap_cli = cliente.get("CAP", "")
    com_cli = cliente.get("Comune", "")
    prov_cli = cliente.get("Provincia", "")
    piva_cli = cliente.get("PIVA", "")
    cf_cli = cliente.get("CF", "")
    cod_dest = cliente.get("CodiceDestinatario", "") or "0000000"
    pec_dest = cliente.get("PEC", "") or ""

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
    if cf_cli:
        pdf.set_x(120)
        pdf.cell(0, 4, f"CODICE FISCALE {cf_cli}", ln=1)

    pdf.ln(5)

    # DATI DOCUMENTO / TRASMISSIONE
    pdf.set_fill_color(31, 119, 180)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)

    pdf.set_x(10)
    pdf.cell(95, 7, "DATI DOCUMENTO", border=1, ln=0, fill=True)
    pdf.cell(95, 7, "DATI TRASMISSIONE", border=1, ln=1, fill=True)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)

    pdf.set_x(10)
    pdf.cell(25, 6, "TIPO", border=1)
    pdf.cell(70, 6, "TD01 FATTURA - B2B", border=1, ln=1)

    pdf.set_x(10)
    pdf.cell(25, 6, "NUMERO", border=1)
    pdf.cell(70, 6, str(numero), border=1, ln=1)

    pdf.set_x(10)
    pdf.cell(25, 6, "DATA", border=1)
    pdf.cell(70, 6, data_f.strftime("%d/%m/%Y"), border=1, ln=1)

    causale = ""
    if righe:
        causale = (righe[0].get("desc") or "").replace("\n", " ").strip()
        if len(causale) > 40:
            causale = causale[:37] + "..."
    if not causale:
        causale = "SERVIZI PROFESSIONALI"

    pdf.set_x(10)
    pdf.cell(25, 6, "CAUSALE", border=1)
    pdf.cell(70, 6, causale, border=1, ln=1)

    pdf.set_xy(105, pdf.get_y() - 24)
    pdf.cell(35, 6, "CODICE DESTINATARIO", border=1)
    pdf.cell(60, 6, cod_dest, border=1, ln=1)

    pdf.set_x(105)
    pdf.cell(35, 6, "PEC DESTINATARIO", border=1)
    pdf.cell(60, 6, pec_dest, border=1, ln=1)

    pdf.set_x(105)
    pdf.cell(35, 6, "DATA INVIO", border=1)
    pdf.cell(60, 6, "", border=1, ln=1)

    pdf.set_x(105)
    pdf.cell(35, 6, "IDENTIFICATIVO SDI", border=1)
    pdf.cell(60, 6, "", border=1, ln=1)

    pdf.ln(4)

    # DETTAGLIO DOCUMENTO
    pdf.set_fill_color(31, 119, 180)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_x(10)
    pdf.cell(190, 7, "DETTAGLIO DOCUMENTO", border=1, ln=1, fill=True)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_x(10)
    pdf.cell(8, 6, "#", border=1)
    pdf.cell(80, 6, "DESCRIZIONE", border=1)
    pdf.cell(12, 6, "U.M.", border=1)
    pdf.cell(25, 6, "PREZZO", border=1)
    pdf.cell(20, 6, "QTA", border=1)
    pdf.cell(25, 6, "TOTALE", border=1)
    pdf.cell(20, 6, "IVA %", border=1, ln=1)

    pdf.set_font("Helvetica", "", 9)
    riepilogo_iva = {}

    for idx, r in enumerate(righe, start=1):
        desc = (r.get("desc") or "").replace("\n", " ").strip()
        if len(desc) > 60:
            desc = desc[:57] + "..."

        qta = float(r.get("qta", 0))
        prezzo = float(r.get("prezzo", 0.0))
        iva_perc = int(r.get("iva", 0))

        imp_riga = qta * prezzo
        iva_riga = imp_riga * iva_perc / 100

        if iva_perc not in riepilogo_iva:
            riepilogo_iva[iva_perc] = {"imp": 0.0, "iva": 0.0}
        riepilogo_iva[iva_perc]["imp"] += imp_riga
        riepilogo_iva[iva_perc]["iva"] += iva_riga

        pdf.set_x(10)
        pdf.cell(8, 6, str(idx), border=1)
        pdf.cell(80, 6, desc, border=1)
        pdf.cell(12, 6, "", border=1)
        pdf.cell(25, 6, _format_val_eur(prezzo), border=1, align="R")
        pdf.cell(20, 6, f"{qta:.2f}".replace(".", ","), border=1, align="R")
        pdf.cell(25, 6, _format_val_eur(imp_riga), border=1, align="R")
        pdf.cell(20, 6, f"{iva_perc:.0f}", border=1, align="R", ln=1)

    pdf.ln(2)

    # IMPORTI / NETTO A PAGARE
    pdf.set_font("Helvetica", "", 9)
    x_left = 10
    x_right = 120

    pdf.set_x(x_left)
    pdf.cell(40, 5, "IMPORTO", ln=0)
    pdf.set_x(x_right)
    pdf.cell(40, 5, _format_val_eur(imponibile), ln=1, align="R")

    pdf.set_x(x_left)
    pdf.cell(40, 5, "TOTALE IMPONIBILE", ln=0)
    pdf.set_x(x_right)
    pdf.cell(40, 5, _format_val_eur(imponibile), ln=1, align="R")

    pdf.set_x(x_left)
    pdf.cell(60, 5, f"IVA (SU IMPORTO {_format_val_eur(imponibile)})", ln=0)
    pdf.set_x(x_right)
    pdf.cell(40, 5, "+ " + _format_val_eur(iva), ln=1, align="R")

    pdf.set_x(x_left)
    pdf.cell(40, 5, "IMPORTO TOTALE", ln=0)
    pdf.set_x(x_right)
    pdf.cell(40, 5, _format_val_eur(totale), ln=1, align="R")

    pdf.set_x(x_left)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(40, 6, "NETTO A PAGARE", ln=0)
    pdf.set_x(x_right)
    pdf.cell(40, 6, _format_val_eur(totale), ln=1, align="R")

    pdf.ln(4)

    # RIEPILOGHI IVA
    pdf.set_fill_color(31, 119, 180)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_x(10)
    pdf.cell(190, 7, "RIEPILOGHI", border=1, ln=1, fill=True)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_x(10)
    pdf.cell(15, 6, "IVA %", border=1)
    pdf.cell(35, 6, "NAT.", border=1)
    pdf.cell(40, 6, "RIF. NORMATIVO", border=1)
    pdf.cell(30, 6, "IMPONIBILE", border=1)
    pdf.cell(25, 6, "IMPOSTA", border=1)
    pdf.cell(20, 6, "ESIG. IVA", border=1)
    pdf.cell(25, 6, "TOTALE", border=1, ln=1)

    pdf.set_font("Helvetica", "", 8)
    for aliquota, dati in riepilogo_iva.items():
        imp = dati["imp"]
        iv = dati["iva"]
        tot = imp + iv
        pdf.set_x(10)
        pdf.cell(15, 6, f"{aliquota:.0f}", border=1)
        pdf.cell(35, 6, "", border=1)
        pdf.cell(40, 6, "", border=1)
        pdf.cell(30, 6, _format_val_eur(imp), border=1, align="R")
        pdf.cell(25, 6, _format_val_eur(iv), border=1, align="R")
        pdf.cell(20, 6, "IMMEDIATA", border=1)
        pdf.cell(25, 6, _format_val_eur(tot), border=1, align="R", ln=1)

    pdf.ln(4)

    # MODALITÀ DI PAGAMENTO
    pdf.set_fill_color(31, 119, 180)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_x(10)
    pdf.cell(
        190,
        7,
        "MODALITÀ DI PAGAMENTO ACCETTATE: PAGAMENTO COMPLETO",
        border=1,
        ln=1,
        fill=True,
    )

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_x(10)
    pdf.cell(40, 6, "MODALITA'", border=1)
    pdf.cell(80, 6, "DETTAGLI", border=1)
    pdf.cell(35, 6, "DATA RIF. TERMINI", border=1)
    pdf.cell(35, 6, "DATA SCADENZA", border=1, ln=1)

    if modalita_pagamento:
        metodo = modalita_pagamento.split()[0].upper()[:20]
        dettagli = modalita_pagamento[:60]
    else:
        metodo = "BONIFICO"
        dettagli = ""

    pdf.set_font("Helvetica", "", 8)
    pdf.set_x(10)
    pdf.cell(40, 6, metodo, border=1)
    pdf.cell(80, 6, dettagli, border=1)
    pdf.cell(35, 6, "", border=1)
    pdf.cell(35, 6, "", border=1, ln=1)

    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_x(10)
    pdf.cell(60, 5, f"TOTALE A PAGARE EUR {_format_val_eur(totale)}", ln=1)

    # NOTE
    if note and note.strip():
        pdf.ln(3)
        pdf.set_fill_color(31, 119, 180)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_x(10)
        pdf.cell(190, 7, "NOTE", border=1, ln=1, fill=True)

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_x(10)
        pdf.multi_cell(190, 4, note, border=1)

    # NOTA FINALE
    pdf.set_y(270)
    pdf.set_font("Helvetica", "I", 7)
    pdf.multi_cell(
        0,
        4,
        "Copia di cortesia priva di valore fiscale e giuridico ai sensi dell'art. 21 del D.P.R. 633/72. "
        "L'originale è consultabile nel portale Fatture e Corrispettivi dell'Agenzia delle Entrate.",
    )

    data = pdf.output(dest="S")
    return bytes(data)


# ==========================
# SIDEBAR: NAVIGAZIONE
# ==========================
PAGINE = [
    "Lista documenti",
    "Crea nuova fattura",
    "Download (documenti inviati)",
    "Carica pacchetto AdE",
    "Rubrica",
    "Dashboard",
]

pagina_default = st.session_state.pagina_corrente
if pagina_default not in PAGINE:
    pagina_default = "Dashboard"
default_index = PAGINE.index(pagina_default)

with st.sidebar:
    st.markdown("### 📄 Documenti")
    pagina = st.radio(
        "",
        PAGINE,
        index=default_index,
        label_visibility="collapsed",
    )

st.session_state.pagina_corrente = pagina

# ==========================
# HEADER SUPERIORE
# ==========================
col_logo, col_menu, col_user = st.columns([2, 5, 1])
with col_logo:
    st.markdown(
        f"<h1 style='color:{PRIMARY_BLUE};margin-bottom:0'>FISCO CHIARO CONSULTING</h1>",
        unsafe_allow_html=True,
    )
with col_menu:
    st.markdown("#### Dashboard | Clienti | Documenti")
with col_user:
    st.markdown("Operatore")

st.markdown("---")

# ==========================
# BARRA FRONTALE
# ==========================
barra_ricerca = ""
tabs = None
idx_mese = date.today().month

if pagina in [
    "Lista documenti",
    "Crea nuova fattura",
    "Download (documenti inviati)",
    "Carica pacchetto AdE",
]:
    col_search, col_stato, col_emesse, col_ricevute, col_agg = st.columns(
        [4, 1, 1, 1, 1]
    )
    with col_search:
        barra_ricerca = st.text_input(
            " ",
            placeholder="Id fiscale, denominazione, causale, tag",
            label_visibility="collapsed",
        )
    with col_stato:
        if st.button("STATO"):
            st.session_state.pagina_corrente = "Dashboard"
            st.rerun()
    with col_emesse:
        if st.button("EMESSE"):
            st.session_state.pagina_corrente = "Lista documenti"
            st.rerun()
    with col_ricevute:
        if st.button("RICEVUTE"):
            st.session_state.pagina_corrente = "Download (documenti inviati)"
            st.rerun()
    with col_agg:
        st.button("AGGIORNA")

    mesi = [
        "Riepilogo",
        "Gennaio",
        "Febbraio",
        "Marzo",
        "Aprile",
        "Maggio",
        "Giugno",
        "Luglio",
        "Agosto",
        "Settembre",
        "Ottobre",
        "Novembre",
        "Dicembre",
    ]
    tabs = st.tabs(mesi)
    idx_mese = date.today().month  # 1-12


# ==========================
# PAGINA: LISTA DOCUMENTI
# ==========================
if pagina == "Lista documenti":
    st.subheader("Lista documenti")

    df_e_all = st.session_state.documenti_emessi.copy()

    if tabs is not None:
        # TAB RIEPILOGO (indice 0)
        with tabs[0]:
            crea_riepilogo_fatture_emesse(df_e_all)

        # TAB MESE CORRENTE (come prima)
        with tabs[idx_mese]:
            df_e = df_e_all.copy()

            if not df_e.empty:
                if barra_ricerca:
                    mask = (
                        df_e["Numero"]
                        .astype(str)
                        .str.contains(barra_ricerca, case=False, na=False)
                        | df_e["Controparte"]
                        .astype(str)
                        .str.contains(barra_ricerca, case=False, na=False)
                    )
                    df_e = df_e[mask]

                # filtro per mese corrente
                df_e["Data"] = pd.to_datetime(df_e["Data"], errors="coerce")
                df_e = df_e[df_e["Data"].dt.month == idx_mese]

                if not df_e.empty:
                    st.dataframe(
                        df_e.drop(columns=["PDF"]),
                        use_container_width=True,
                        height=400,
                    )
                else:
                    st.info("Nessun documento emesso per il mese selezionato.")
            else:
                st.info("Nessun documento emesso presente.")

    st.markdown("### 📄 Download PDF fatture emesse")
    df_e = st.session_state.documenti_emessi
    if df_e.empty:
        st.caption("Nessuna fattura emessa salvata nell'app.")
    else:
        df_e_pdf = df_e[df_e["PDF"] != ""]
        if df_e_pdf.empty:
            st.caption("Le fatture emesse non hanno ancora PDF associati.")
        else:
            numeri = df_e_pdf["Numero"].tolist()
            scelta_num = st.selectbox("Seleziona fattura emessa", numeri)
            if scelta_num:
                riga = df_e_pdf[df_e_pdf["Numero"] == scelta_num].iloc[0]
                pdf_path = riga["PDF"]
                if os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()
                    st.download_button(
                        label=f"📥 Scarica PDF fattura {scelta_num}",
                        data=pdf_bytes,
                        file_name=os.path.basename(pdf_path),
                        mime="application/pdf",
                    )
                    st.markdown("#### Anteprima PDF")
                    mostra_anteprima_pdf(pdf_bytes, altezza=500)
                else:
                    st.warning("Il file PDF indicato non esiste più sul disco.")

# ==========================
# PAGINA: CREA NUOVA FATTURA
# ==========================
elif pagina == "Crea nuova fattura":
    st.subheader("Crea nuova fattura emessa")

    denominazioni = ["NUOVO"] + st.session_state.clienti["Denominazione"].tolist()

    col1, col2 = st.columns([2, 1])
    with col1:
        current_label = st.session_state.cliente_corrente_label
        if current_label not in denominazioni:
            current_label = "NUOVO"
        default_idx = denominazioni.index(current_label)

        cliente_sel = st.selectbox(
            "Cliente",
            denominazioni,
