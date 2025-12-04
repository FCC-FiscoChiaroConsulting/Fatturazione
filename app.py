import streamlit as st
import pandas as pd
from datetime import date
import requests
import os
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ==========================
# CONFIGURAZIONE PAGINA
# ==========================
st.set_page_config(
    page_title="Fisco Chiaro - Fatturazione elettronica",
    layout="wide",
    page_icon="📄"
)

# Cartella locale per i PDF
PDF_DIR = "fatture_pdf"
os.makedirs(PDF_DIR, exist_ok=True)

# ==========================
# STATO DI SESSIONE
# ==========================
COLONNE_DOC = ["Tipo", "Numero", "Data", "Controparte", "Importo", "Stato", "UUID", "PDF"]

if "documenti_emessi" not in st.session_state:
    st.session_state.documenti_emessi = pd.DataFrame(columns=COLONNE_DOC)

if "ultimo_uuid" not in st.session_state:
    st.session_state.ultimo_uuid = ""

if "ultimo_pdf_bytes" not in st.session_state:
    st.session_state.ultimo_pdf_bytes = None
if "ultimo_pdf_nome" not in st.session_state:
    st.session_state.ultimo_pdf_nome = ""


# ==========================
# SIDEBAR STILE GESTIONALE
# ==========================
with st.sidebar:
    st.markdown("### ⚙️ Configurazione Openapi")

    ambiente = st.selectbox(
        "Ambiente",
        ["Sandbox (test)", "Produzione"],
        index=0,
        help="Imposta l'ambiente corrispondente alle credenziali Openapi."
    )

    # ⚠️ Sostituisci questi URL con quelli indicati nella console Openapi
    if ambiente.startswith("Sandbox"):
        BASE_URL = "https://API_SANDBOX_SDI_OPENAPI"  # es. https://api-sandbox.openapi.com/sdi
    else:
        BASE_URL = "https://API_PRODUZIONE_SDI_OPENAPI"  # es. https://api.openapi.com/sdi

    api_key = st.text_input(
        "API Key Openapi",
        type="password",
        help="Copia qui il token Bearer dalla console Openapi."
    )

    st.markdown("---")
    st.markdown("### 📑 Menu")

    pagina = st.radio(
        "",
        ["Lista documenti", "Crea fattura", "Invia XML", "Stato fattura", "Dashboard"],
        label_visibility="collapsed"
    )

# ==========================
# HEADER SUPERIORE
# ==========================
col_logo, col_menu, col_user = st.columns([1, 5, 1])

with col_logo:
    st.markdown("## FISCO CHIARO")

with col_menu:
    st.markdown("#### Documenti | Clienti | SDI")

with col_user:
    st.markdown("Operatore")

st.markdown("---")


# ==========================
# FUNZIONI DI SUPPORTO
# ==========================

def _check_api() -> bool:
    """Controlla che API key e BASE_URL siano configurati in modo sensato."""
    if not api_key:
        st.error("Inserisci l'API Key Openapi nella sidebar per usare le funzioni SDI.")
        return False
    if "API_SANDBOX" in BASE_URL or "API_PRODUZIONE" in BASE_URL:
        st.error("Configura i corretti URL BASE_URL per sandbox/produzione prima di usare le API.")
        return False
    return True


def genera_pdf_fattura(numero: str, data_f: date, controparte: str, importo: float) -> bytes:
    """
    Genera un PDF semplice della fattura (fattura pro-forma lato app)
    e restituisce i bytes del file.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    larghezza, altezza = A4

    # Intestazione semplice stile FCC
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, altezza - 60, "FISCO CHIARO CONSULTING")

    c.setFont("Helvetica", 10)
    c.drawString(40, altezza - 80, "Fattura emessa (app)")
    c.drawString(40, altezza - 95, f"Numero: {numero}")
    c.drawString(40, altezza - 110, f"Data: {data_f.strftime('%d/%m/%Y')}")

    # Dati cliente
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, altezza - 140, "Cliente / Controparte:")
    c.setFont("Helvetica", 10)
    c.drawString(40, altezza - 155, controparte if controparte else "-")

    # Riepilogo economico
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, altezza - 190, "Riepilogo:")
    c.setFont("Helvetica", 10)
    c.drawString(60, altezza - 210, f"Importo totale: € {importo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    # Nota finale
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(40, 60, "Documento generato dall'app Fisco Chiaro (uso interno / invio cliente).")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()


@st.cache_data(ttl=60)
def get_fatture_ricevute(api_key: str, base_url: str) -> pd.DataFrame:
    """
    Lettura fatture passive (ricevute da SdI) via Openapi.
    Adatta la struttura ai campi restituiti dalla tua istanza reale.
    """
    if not api_key:
        return pd.DataFrame(columns=COLONNE_DOC)

    headers = {"Authorization": f"Bearer {api_key}"}
    # Parametri di esempio: verifica con la documentazione Openapi
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
                "Controparte": inv.get("counterparty", {}).get("name"),
                "Importo": inv.get("totals", {}).get("grandTotal"),
                "Stato": inv.get("status"),
                "UUID": inv.get("uuid") or inv.get("id"),
                "PDF": ""   # per le ricevute non generiamo PDF locale
            })
        df = pd.DataFrame(righe, columns=COLONNE_DOC)
        return df

    except Exception as e:
        st.error(f"Errore connessione Openapi: {e}")
        return pd.DataFrame(columns=COLONNE_DOC)


def invia_xml_sdi(xml_bytes: bytes, apply_signature: bool, apply_legal: bool) -> dict:
    """
    Invia un file XML allo SDI tramite Openapi usando POST /invoices.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/xml"
    }

    params = {
        "apply_signature": str(apply_signature).lower(),
        "apply_legal_storage": str(apply_legal).lower(),
    }

    url = f"{BASE_URL}/invoices"

    r = requests.post(url, headers=headers, params=params, data=xml_bytes, timeout=30)
    esito = {
        "status_code": r.status_code,
        "raw": r.text
    }

    try:
        esito["json"] = r.json()
    except Exception:
        esito["json"] = None

    return esito


def get_stato_fattura(uuid: str) -> dict:
    """
    Recupera lo stato di una singola fattura tramite GET /invoices/{uuid}.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{BASE_URL}/invoices/{uuid}"

    r = requests.get(url, headers=headers, timeout=20)
    esito = {
        "status_code": r.status_code,
        "raw": r.text
    }
    try:
        esito["json"] = r.json()
    except Exception:
        esito["json"] = None
    return esito


# ==========================
# PAGINE
# ==========================

# 1) LISTA DOCUMENTI (emesse locali + ricevute da Openapi)
if pagina == "Lista documenti":
    st.subheader("Lista documenti")

    col_cerca, col_stato, col_emesse, col_ricevute, col_agg = st.columns([3, 2, 1, 1, 1])
    with col_cerca:
        testo = st.text_input("Ricerca", placeholder="Numero, controparte...")
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
                st.warning("Inserisci API Key Openapi nella sidebar per vedere le fatture ricevute da SdI.")
            elif _check_api():
                df_r = get_fatture_ricevute(api_key, BASE_URL)
                if not df_r.empty:
                    frames.append(df_r)

        if frames:
            df = pd.concat(frames, ignore_index=True)

            if testo:
                mask = (
                    df["Numero"].astype(str).str.contains(testo, case=False, na=False) |
                    df["Controparte"].astype(str).str.contains(testo, case=False, na=False)
                )
                df = df[mask]

            if stato_filtro != "TUTTI":
                df = df[df["Stato"] == stato_filtro]

            st.dataframe(df.drop(columns=["PDF"]), use_container_width=True, height=450)
        else:
            st.info("Nessun documento da mostrare per i filtri selezionati.")

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
                        mime="application/pdf"
                    )
                else:
                    st.warning("Il file PDF indicato non esiste più sul disco.")


# 2) CREA FATTURA (SOLO EMESSA, LOCALE + PDF)
elif pagina == "Crea fattura":
    st.subheader("Crea nuova fattura emessa (solo lato app)")

    num_default = f"FT{date.today().strftime('%y%m%d')}-001"

    col1, col2 = st.columns(2)
    with col1:
        numero = st.text_input("Numero", num_default)
        data_f = st.date_input("Data", date.today())
    with col2:
        controparte = st.text_input("Cliente / Controparte")
        importo = st.number_input("Importo (lordo)", min_value=0.0, value=0.0)

    stato = st.selectbox("Stato", ["Bozza", "Inviata", "Registrata"])

    if st.button("💾 Salva fattura emessa", type="primary"):
        # Genera PDF
        pdf_bytes = genera_pdf_fattura(numero, data_f, controparte, importo)
        pdf_filename = f"{numero.replace('/', '_')}.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_filename)
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        nuova = pd.DataFrame([{
            "Tipo": "Emessa",
            "Numero": numero,
            "Data": str(data_f),
            "Controparte": controparte,
            "Importo": importo,
            "Stato": stato,
            "UUID": "",
            "PDF": pdf_path
        }], columns=COLONNE_DOC)

        st.session_state.documenti_emessi = pd.concat(
            [st.session_state.documenti_emessi, nuova],
            ignore_index=True
        )

        st.session_state.ultimo_pdf_bytes = pdf_bytes
        st.session_state.ultimo_pdf_nome = pdf_filename

        st.success("✅ Fattura emessa salvata (solo lato app, non inviata a SdI).")
        st.markdown("#### 📄 PDF generato")

        st.download_button(
            label="📥 Scarica subito il PDF",
            data=pdf_bytes,
            file_name=pdf_filename,
            mime="application/pdf"
        )


# 3) INVIA XML A SDI VIA OPENAPI
elif pagina == "Invia XML":
    st.subheader("Invia fattura elettronica XML allo SDI (Openapi)")

    st.caption("Carica un file XML FatturaPA già generato e invialo tramite POST /invoices.")

    uploaded_xml = st.file_uploader("Carica file XML", type=["xml"])

    col1, col2 = st.columns(2)
    with col1:
        apply_signature = st.checkbox("Firma elettronica (se abilitata in Openapi)", value=True)
    with col2:
        apply_legal = st.checkbox("Conservazione a norma (se abilitata)", value=True)

    if st.button("🚀 Invia allo SDI"):
        if not _check_api():
            pass
        elif not uploaded_xml:
            st.error("Carica prima un file XML.")
        else:
            xml_bytes = uploaded_xml.read()

            with st.expander("Richiesta HTTP (debug)", expanded=False):
                st.code(
                    f"POST {BASE_URL}/invoices\n"
                    f"Authorization: Bearer ******\n"
                    f"Content-Type: application/xml\n\n"
                    f"<XML fattura…>",
                    language="http"
                )

            with st.spinner("Invio in corso…"):
                esito = invia_xml_sdi(xml_bytes, apply_signature, apply_legal)

            st.markdown("### 📥 Risposta Openapi")
            st.write("Status code:", esito["status_code"])
            st.code(esito["raw"])

            if esito["json"]:
                st.json(esito["json"])
                uuid = esito["json"].get("uuid") or esito["json"].get("id")
                if uuid:
                    st.session_state.ultimo_uuid = uuid
                    st.success(f"✅ Fattura caricata. UUID: {uuid}")


# 4) STATO FATTURA SDI
elif pagina == "Stato fattura":
    st.subheader("Stato fattura SDI (Openapi)")

    default_uuid = st.session_state.ultimo_uuid or ""
    uuid = st.text_input("UUID fattura", value=default_uuid, help="UUID restituito da Openapi dopo l'invio.")

    if st.button("🔍 Recupera stato"):
        if not _check_api():
            pass
        elif not uuid:
            st.error("Inserisci l'UUID della fattura.")
        else:
            with st.expander("Richiesta HTTP (debug)", expanded=False):
                st.code(
                    f"GET {BASE_URL}/invoices/{uuid}\nAuthorization: Bearer ******",
                    language="http"
                )

            with st.spinner("Richiesta in corso…"):
                esito = get_stato_fattura(uuid)

            st.write("Status code:", esito["status_code"])
            st.code(esito["raw"])

            if esito["json"]:
                st.json(esito["json"])


# 5) DASHBOARD SINTETICA
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
    col2.metric("Totale emesso", f"€{tot_emesse:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col3.metric("Fatture ricevute (SdI)", num_ricevute)
    col4.metric("Totale ricevuto", f"€{tot_ricevute:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    st.markdown("---")
    st.caption("Fisco Chiaro – Emesse gestite dall'app; ricezione, invio e stato via Openapi SDI.")
