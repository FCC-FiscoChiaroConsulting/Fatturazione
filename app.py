import streamlit as st
import pandas as pd
from datetime import date
import requests

# ==========================
# CONFIGURAZIONE PAGINA
# ==========================
st.set_page_config(
    page_title="Fisco Chiaro Consulting - Fatturazione elettronica",
    layout="wide",
    page_icon="📄"
)

# ==========================
# STATO DI SESSIONE
# ==========================
COLONNE_DOC = ["Tipo", "Numero", "Data", "Controparte", "Importo", "Stato", "UUID"]

if "documenti_emessi" not in st.session_state:
    st.session_state.documenti_emessi = pd.DataFrame(columns=COLONNE_DOC)

if "ultimo_uuid" not in st.session_state:
    st.session_state.ultimo_uuid = ""

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
    st.markdown("## FISCO CHIARO CONSULTING")

with col_menu:
    st.markdown("#### Documenti | Clienti | SDI")

with col_user:
    st.markdown("Operatore")

st.markdown("---")


# ==========================
# FUNZIONI DI SUPPORTO OPENAPI
# ==========================

def _check_api():
    if not api_key:
        st.error("Inserisci l'API Key Openapi nella sidebar per usare le funzioni SDI.")
        return False
    if "API_SANDBOX" in BASE_URL or "API_PRODUZIONE" in BASE_URL:
        st.error("Configura i corretti URL BASE_URL per sandbox/produzione prima di usare le API.")
        return False
    return True


@st.cache_data(ttl=60)
def get_fatture_ricevute(api_key: str, base_url: str) -> pd.DataFrame:
    """
    Lettura fatture passive (ricevute da SdI).
    La struttura esatta della risposta può variare: adatta i campi ai tuoi dati reali.
    """
    if not api_key:
        return pd.DataFrame(columns=COLONNE_DOC)

    headers = {"Authorization": f"Bearer {api_key}"}
    # Nota: il parametro "type=1" è un esempio. Verifica nella documentazione Openapi
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
                "UUID": inv.get("uuid") or inv.get("id")
            })
        df = pd.DataFrame(righe, columns=COLONNE_DOC)
        return df

    except Exception as e:
        st.error(f"Errore connessione Openapi: {e}")
        return pd.DataFrame(columns=COLONNE_DOC)


def invia_xml_sdi(xml_bytes: bytes, apply_signature: bool, apply_legal: bool) -> dict:
    """
    Invia un file XML allo SDI tramite Openapi usando POST /invoices.
    Vedi documentazione Fatturazione Elettronica SDI. 
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/xml"
    }

    # alcune configurazioni (firma / conservazione) in Openapi si gestiscono lato
    # business configuration; qui uso querystring come esempio generico.
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

            st.dataframe(df, use_container_width=True, height=450)
        else:
            st.info("Nessun documento da mostrare per i filtri selezionati.")


# 2) CREA FATTURA (SOLO EMESSA, LOCALE)
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
        nuova = pd.DataFrame([{
            "Tipo": "Emessa",
            "Numero": numero,
            "Data": str(data_f),
            "Controparte": controparte,
            "Importo": importo,
            "Stato": stato,
            "UUID": ""
        }], columns=COLONNE_DOC)

        st.session_state.documenti_emessi = pd.concat(
            [st.session_state.documenti_emessi, nuova],
            ignore_index=True
        )
        st.success("✅ Fattura emessa salvata (solo lato app, non inviata a SdI).")


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

