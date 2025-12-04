import streamlit as st
import pandas as pd
from datetime import date
import requests
import os
from fpdf import FPDF

# ==========================
# CONFIGURAZIONE PAGINA
# ==========================
st.set_page_config(
    page_title="Fisco Chiaro Consulting - Fatture",
    layout="wide",
    page_icon="📄"
)

PRIMARY_BLUE = "#1f77b4"  # blu Fisco Chiaro

# Cartella locale per i PDF
PDF_DIR = "fatture_pdf"
os.makedirs(PDF_DIR, exist_ok=True)

# ==========================
# STATO DI SESSIONE
# ==========================
COLONNE_DOC = ["Tipo", "Numero", "Data", "Cliente", "PIVA", "Importo", "Stato", "UUID", "PDF"]

if "documenti_emessi" not in st.session_state:
    st.session_state.documenti_emessi = pd.DataFrame(columns=COLONNE_DOC)

if "clienti" not in st.session_state:
    st.session_state.clienti = pd.DataFrame(columns=["Denominazione", "PIVA", "Indirizzo"])

if "righe_correnti" not in st.session_state:
    st.session_state.righe_correnti = []

if "ultimo_uuid" not in st.session_state:
    st.session_state.ultimo_uuid = ""

# ==========================
# SIDEBAR
# ==========================
with st.sidebar:
    st.markdown(f"<h2 style='color:{PRIMARY_BLUE}'>⚙️ Configurazione</h2>", unsafe_allow_html=True)
    ambiente = st.selectbox(
        "Ambiente Openapi",
        ["Sandbox (test)", "Produzione"],
        index=0
    )
    if ambiente.startswith("Sandbox"):
        BASE_URL = "https://API_SANDBOX_SDI_OPENAPI"  # sostituisci con URL reale sandbox
    else:
        BASE_URL = "https://API_PRODUZIONE_SDI_OPENAPI"  # sostituisci con URL reale produzione

    api_key = st.text_input("API Key Openapi", type="password")

    st.markdown("---")
    st.markdown("### 📑 Menu")
    pagina = st.radio(
        "",
        ["Lista documenti", "Crea fattura", "Clienti", "Invia XML", "Stato fattura", "Dashboard"],
        label_visibility="collapsed"
    )

# ==========================
# HEADER
# ==========================
col_logo, col_menu, col_user = st.columns([2, 5, 1])
with col_logo:
    st.markdown(f"<h1 style='color:{PRIMARY_BLUE};margin-bottom:0'>FISCO CHIARO CONSULTING</h1>", unsafe_allow_html=True)
with col_menu:
    st.markdown("#### Documenti | Clienti | SDI")
with col_user:
    st.markdown("Operatore")

st.markdown("---")

# ==========================
# FUNZIONI DI SUPPORTO
# ==========================

def _check_api() -> bool:
    if not api_key:
        st.error("Inserisci l'API Key Openapi nella sidebar per usare le funzioni SDI.")
        return False
    if "API_SANDBOX" in BASE_URL or "API_PRODUZIONE" in BASE_URL:
        st.error("Configura i corretti URL BASE_URL per sandbox/produzione prima di usare le API.")
        return False
    return True


def genera_pdf_fattura(numero: str, data_f: date, cliente: dict, righe: list, imponibile: float, iva: float, totale: float) -> bytes:
    """Genera PDF semplice della fattura (senza simbolo € per evitare problemi font)."""
    pdf = FPDF()
    pdf.add_page()

    # Intestazione blu
    pdf.set_text_color(31, 119, 180)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "FISCO CHIARO CONSULTING", ln=1)
    pdf.set_text_color(0, 0, 0)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "Fattura emessa (uso interno / cliente)", ln=1)
    pdf.cell(0, 8, f"Numero: {numero}", ln=1)
    pdf.cell(0, 8, f"Data: {data_f.strftime('%d/%m/%Y')}", ln=1)
    pdf.ln(4)

    # Dati cliente
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Cliente:", ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, cliente.get("Denominazione", "-"), ln=1)
    pdf.cell(0, 8, f"P.IVA/CF: {cliente.get('PIVA', '-')}", ln=1)
    if cliente.get("Indirizzo"):
        pdf.multi_cell(0, 6, cliente["Indirizzo"])
    pdf.ln(4)

    # Righe
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Righe fattura:", ln=1)
    pdf.set_font("Helvetica", "", 10)
    for r in righe:
        riga_txt = f"- {r['desc']} | {r['qta']} x {r['prezzo']:.2f} (IVA {r['iva']}%)"
        pdf.multi_cell(0, 6, riga_txt)
    pdf.ln(4)

    # Riepilogo economico (senza simbolo € per evitare UnicodeError)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Riepilogo:", ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, f"Imponibile: EUR {imponibile:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), ln=1)
    pdf.cell(0, 6, f"IVA: EUR {iva:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), ln=1)
    pdf.cell(0, 6, f"Totale: EUR {totale:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), ln=1)

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, "Documento generato dall'app Fisco Chiaro Consulting.")

    return pdf.output(dest="S").encode("latin-1")


@st.cache_data(ttl=60)
def get_fatture_ricevute(api_key: str, base_url: str) -> pd.DataFrame:
    """Lettura fatture passive (ricevute) da Openapi: type=1. Solo lettura."""
    if not api_key:
        return pd.DataFrame(columns=COLONNE_DOC)
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"type": 1}
    try:
        r = requests.get(f"{base_url}/invoices", headers=headers, params=params, timeout=20)
        if r.status_code != 200:
            st.error(f"Errore Openapi {r.status_code}: {r.text}")
            return pd.DataFrame(columns=COLONNE_DOC)
        data = r.json()
        fatture = data.get("data", data)
        righe = []
        for inv in fatture:
            righe.append({
                "Tipo": "Ricevuta",
                "Numero": inv.get("number"),
                "Data": inv.get("date"),
                "Cliente": inv.get("counterparty", {}).get("name"),
                "PIVA": inv.get("counterparty", {}).get("vatNumber"),
                "Importo": inv.get("totals", {}).get("grandTotal"),
                "Stato": inv.get("status"),
                "UUID": inv.get("uuid") or inv.get("id"),
                "PDF": ""
            })
        return pd.DataFrame(righe, columns=COLONNE_DOC)
    except Exception as e:
        st.error(f"Errore connessione Openapi: {e}")
        return pd.DataFrame(columns=COLONNE_DOC)


def invia_xml_sdi(xml_bytes: bytes, apply_signature: bool, apply_legal: bool) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/xml"}
    params = {
        "apply_signature": str(apply_signature).lower(),
        "apply_legal_storage": str(apply_legal).lower(),
    }
    url = f"{BASE_URL}/invoices"
    r = requests.post(url, headers=headers, params=params, data=xml_bytes, timeout=30)
    esito = {"status_code": r.status_code, "raw": r.text}
    try:
        esito["json"] = r.json()
    except Exception:
        esito["json"] = None
    return esito


def get_stato_fattura(uuid: str) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{BASE_URL}/invoices/{uuid}"
    r = requests.get(url, headers=headers, timeout=20)
    esito = {"status_code": r.status_code, "raw": r.text}
    try:
        esito["json"] = r.json()
    except Exception:
        esito["json"] = None
    return esito

# ==========================
# PAGINE
# ==========================

# 1) LISTA DOCUMENTI
if pagina == "Lista documenti":
    st.subheader("Lista documenti")

    col_cerca, col_stato, col_emesse, col_ricevute, col_agg = st.columns([3, 2, 1, 1, 1])
    with col_cerca:
        testo = st.text_input("Ricerca", placeholder="Numero, cliente...")
    with col_stato:
        stato_filtro = st.selectbox(
            "Stato",
            ["TUTTI", "Bozza", "Inviata", "Registrata", "sent", "received", "accepted", "rejected"]
        )
    with col_emesse:
        show_emesse = st.toggle("Emesse", value=True)
    with col_ricevute:
        show_ricevute = st.toggle("Ricevute", value=True)
    with col_agg:
        refresh = st.button("Aggiorna")

    mesi = [
        "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"
    ]
    tabs = st.tabs(mesi)
    idx_mese = date.today().month - 1

    with tabs[idx_mese]:
        frames = []
        if show_emesse and not st.session_state.documenti_emessi.empty:
            frames.append(st.session_state.documenti_emessi.copy())
        if show_ricevute:
            if not api_key:
                st.warning("Inserisci API Key Openapi per vedere le ricevute da SdI.")
            elif _check_api():
                df_r = get_fatture_ricevute(api_key, BASE_URL)
                if not df_r.empty:
                    frames.append(df_r)

        if frames:
            df = pd.concat(frames, ignore_index=True)
            if testo:
                mask = (
                    df["Numero"].astype(str).str.contains(testo, case=False, na=False) |
                    df["Cliente"].astype(str).str.contains(testo, case=False, na=False)
                )
                df = df[mask]
            if stato_filtro != "TUTTI":
                df = df[df["Stato"] == stato_filtro]
            st.dataframe(df.drop(columns=["PDF"]), use_container_width=True, height=450)
        else:
            st.info("Nessun documento da mostrare per i filtri selezionati.")

# 2) CREA FATTURA EMESSA
elif pagina == "Crea fattura":
    st.subheader("Crea nuova fattura emessa")

    # Selezione cliente
    col1, col2 = st.columns([2, 1])
    denominazioni = ["NUOVO"] + st.session_state.clienti["Denominazione"].tolist()
    with col1:
        cliente_sel = st.selectbox("Cliente", denominazioni)
    with col2:
        nuovo_cli_btn = st.button("➕ Nuovo cliente")

    if cliente_sel == "NUOVO":
        cli_den = st.text_input("Denominazione cliente")
        cli_piva = st.text_input("P.IVA/CF")
        cli_ind = st.text_area("Indirizzo", height=60)
        cliente_corrente = {"Denominazione": cli_den, "PIVA": cli_piva, "Indirizzo": cli_ind}
    else:
        riga_cli = st.session_state.clienti[st.session_state.clienti["Denominazione"] == cliente_sel].iloc[0]
        cli_den = st.text_input("Denominazione", riga_cli["Denominazione"])
        cli_piva = st.text_input("P.IVA/CF", riga_cli["PIVA"])
        cli_ind = st.text_area("Indirizzo", riga_cli["Indirizzo"], height=60)
        cliente_corrente = {"Denominazione": cli_den, "PIVA": cli_piva, "Indirizzo": cli_ind}

    coln1, coln2 = st.columns(2)
    with coln1:
        numero = st.text_input("Numero fattura", f"FT{date.today().strftime('%y%m%d')}-001")
    with coln2:
        data_f = st.date_input("Data fattura", date.today())

    st.markdown("### Righe fattura")
    if st.button("➕ Aggiungi riga"):
        st.session_state.righe_correnti.append({"desc": "", "qta": 1.0, "prezzo": 0.0, "iva": 22})
        st.experimental_rerun()

    imponibile = 0.0
    iva_tot = 0.0

    for i, r in enumerate(st.session_state.righe_correnti):
        c1, c2, c3, c4, c5 = st.columns([4, 1, 1, 1, 0.5])
        with c1:
            r["desc"] = st.text_input("Descrizione", r["desc"], key=f"desc_{i}")
        with c2:
            r["qta"] = st.number_input("Q.tà", min_value=0.0, value=r["qta"], key=f"qta_{i}")
        with c3:
            r["prezzo"] = st.number_input("Prezzo", min_value=0.0, value=r["prezzo"], key=f"prz_{i}")
        with c4:
            r["iva"] = st.selectbox("IVA%", [22, 10, 5, 4, 0], index=[22,10,5,4,0].index(r["iva"]), key=f"iva_{i}")
        with c5:
            if st.button("🗑️", key=f"del_{i}"):
                st.session_state.righe_correnti.pop(i)
                st.experimental_rerun()

        imp_riga = r["qta"] * r["prezzo"]
        iva_riga = imp_riga * r["iva"] / 100
        imponibile += imp_riga
        iva_tot += iva_riga

    totale = imponibile + iva_tot

    col_t1, col_t2, col_t3 = st.columns(3)
    col_t1.metric("Imponibile", f"EUR {imponibile:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col_t2.metric("IVA", f"EUR {iva_tot:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col_t3.metric("Totale", f"EUR {totale:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    stato = st.selectbox("Stato", ["Bozza", "Inviata", "Registrata"])

    if st.button("💾 Salva fattura emessa", type="primary"):
        if not cliente_corrente["Denominazione"]:
            st.error("Inserisci almeno la denominazione del cliente.")
        elif not st.session_state.righe_correnti:
            st.error("Inserisci almeno una riga di fattura.")
        else:
            # se cliente nuovo, aggiungi a rubrica
            if cliente_sel == "NUOVO" and cliente_corrente["Denominazione"]:
                nuova_cli = pd.DataFrame([cliente_corrente])
                st.session_state.clienti = pd.concat([st.session_state.clienti, nuova_cli], ignore_index=True)

            # PDF
            pdf_bytes = genera_pdf_fattura(numero, data_f, cliente_corrente, st.session_state.righe_correnti, imponibile, iva_tot, totale)
            pdf_filename = f"{numero.replace('/', '_')}.pdf"
            pdf_path = os.path.join(PDF_DIR, pdf_filename)
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)

            nuova = pd.DataFrame([{
                "Tipo": "Emessa",
                "Numero": numero,
                "Data": str(data_f),
                "Cliente": cliente_corrente["Denominazione"],
                "PIVA": cliente_corrente["PIVA"],
                "Importo": totale,
                "Stato": stato,
                "UUID": "",
                "PDF": pdf_path
            }], columns=COLONNE_DOC)
            st.session_state.documenti_emessi = pd.concat(
                [st.session_state.documenti_emessi, nuova], ignore_index=True
            )

            st.session_state.righe_correnti = []
            st.success("✅ Fattura emessa salvata (solo lato app, non SdI).")
            st.download_button(
                label="📥 Scarica PDF",
                data=pdf_bytes,
                file_name=pdf_filename,
                mime="application/pdf"
            )

# 3) CLIENTI
elif pagina == "Clienti":
    st.subheader("Rubrica clienti")

    with st.form("nuovo_cliente"):
        col1, col2 = st.columns(2)
        with col1:
            den = st.text_input("Denominazione")
        with col2:
            piva = st.text_input("P.IVA/CF")
        ind = st.text_area("Indirizzo", height=70)
        if st.form_submit_button("💾 Salva cliente"):
            nuovo = pd.DataFrame([{"Denominazione": den, "PIVA": piva, "Indirizzo": ind}])
            st.session_state.clienti = pd.concat([st.session_state.clienti, nuovo], ignore_index=True)
            st.success("Cliente salvato")

    if not st.session_state.clienti.empty:
        st.dataframe(st.session_state.clienti, use_container_width=True)
    else:
        st.info("Nessun cliente in rubrica.")

# 4) INVIA XML
elif pagina == "Invia XML":
    st.subheader("Invia XML FatturaPA a SdI (Openapi)")
    uploaded_xml = st.file_uploader("Carica file XML", type=["xml"])
    col1, col2 = st.columns(2)
    with col1:
        apply_signature = st.checkbox("Firma elettronica (se abilitata)", value=True)
    with col2:
        apply_legal = st.checkbox("Conservazione sostitutiva (se abilitata)", value=True)

    if st.button("🚀 Invia allo SdI"):
        if not _check_api():
            pass
        elif not uploaded_xml:
            st.error("Carica prima un file XML.")
        else:
            xml_bytes = uploaded_xml.read()
            with st.spinner("Invio in corso..."):
                esito = invia_xml_sdi(xml_bytes, apply_signature, apply_legal)
            st.write("Status code:", esito["status_code"])
            st.code(esito["raw"])
            if esito["json"]:
                st.json(esito["json"])
                uuid = esito["json"].get("uuid") or esito["json"].get("id")
                if uuid:
                    st.session_state.ultimo_uuid = uuid
                    st.success(f"UUID memorizzato: {uuid}")

# 5) STATO FATTURA
elif pagina == "Stato fattura":
    st.subheader("Stato fattura SdI (Openapi)")
    default_uuid = st.session_state.ultimo_uuid or ""
    uuid = st.text_input("UUID fattura", value=default_uuid)
    if st.button("🔍 Recupera stato"):
        if not _check_api():
            pass
        elif not uuid:
            st.error("Inserisci UUID.")
        else:
            with st.spinner("Richiesta in corso..."):
                esito = get_stato_fattura(uuid)
            st.write("Status code:", esito["status_code"])
            st.code(esito["raw"])
            if esito["json"]:
                st.json(esito["json"])

# 6) DASHBOARD
else:
    st.subheader("Dashboard")
    df_e = st.session_state.documenti_emessi
    num_emesse = len(df_e)
    tot_emesse = df_e["Importo"].sum() if not df_e.empty else 0

    if api_key and _check_api():
        df_r = get_fatture_ricevute(api_key, BASE_URL)
    else:
        df_r = pd.DataFrame(columns=COLONNE_DOC)

    num_ricevute = len(df_r)
    tot_ricevute = df_r["Importo"].sum() if not df_r.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fatture emesse (app)", num_emesse)
    col2.metric("Totale emesso", f"EUR {tot_emesse:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col3.metric("Fatture ricevute (SdI)", num_ricevute)
    col4.metric("Totale ricevuto", f"EUR {tot_ricevute:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

st.markdown("---")
st.caption("Fisco Chiaro Consulting – Emesse gestite dall'app; ricezione e invio via Openapi SdI.")
