import streamlit as st
import pandas as pd
from datetime import date
import requests

st.set_page_config(page_title="Fisco Chiaro - Fatture", layout="wide", page_icon="📄")

# ==== SESSION STATE (fatture emesse locali) ====
if "documenti_emessi" not in st.session_state:
    st.session_state.documenti_emessi = pd.DataFrame(columns=["Tipo","Numero","Data","Cliente","Importo","Stato"])

# ==== SIDEBAR MENU STILE EFFATTA ====
with st.sidebar:
    st.markdown("### ⚙️ Configurazione")
    api_key = st.text_input("API Key Openapi (solo lettura ricevute)", type="password")
    st.markdown("---")
    st.markdown("### 📑 Menu")
    pagina = st.radio(
        "",
        ["Lista documenti","Crea fattura","Dashboard"],
        label_visibility="collapsed"
    )

# ==== HEADER TOP ====
col_logo, col_menu, col_user = st.columns([1,5,1])
with col_logo:
    st.markdown("## FISCO CHIARO")
with col_menu:
    st.markdown("#### Dashboard | Clienti | Documenti")
with col_user:
    st.markdown("Operatore")

st.markdown("---")

BASE_URL = "https://sdi.openapi.it/invoices"

# ==== FUNZIONE OPENAPI: SOLO FATTURE RICEVUTE (PASSIVE) ====
@st.cache_data(ttl=60)
def get_fatture_ricevute(api_key: str) -> pd.DataFrame:
    """Legge esclusivamente le fatture passive (ricevute) da Openapi, type = 1.
    Nessuna creazione o modifica lato SdI, sola lettura."""
    if not api_key:
        return pd.DataFrame()
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"type": 1}
    try:
        r = requests.get(BASE_URL, headers=headers, params=params, timeout=15)
        if r.status_code != 200:
            st.error(f"Errore Openapi {r.status_code}: {r.text}")
            return pd.DataFrame()
        data = r.json()
        rows = []
        for inv in data.get("data", data):
            rows.append({
                "Tipo": "Ricevuta",
                "Numero": inv.get("number"),
                "Data": inv.get("date"),
                "Cliente/Fornitore": inv.get("counterparty", {}).get("name"),
                "Importo": inv.get("totals", {}).get("grandTotal"),
                "Stato": inv.get("status")
            })
        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"Errore connessione Openapi: {e}")
        return pd.DataFrame()

# ==== PAGINA LISTA DOCUMENTI (EMESSE LOCALI + RICEVUTE OPENAPI) ====
if pagina == "Lista documenti":
    st.subheader("Lista documenti")

    # Barra filtri come Effatta
    col_cerca, col_stato, col_btn_emesse, col_btn_ricevute, col_btn_agg = st.columns([3,2,1,1,1])
    with col_cerca:
        testo = st.text_input("Ricerca", placeholder="Numero, cliente, fornitore...")
    with col_stato:
        stato = st.selectbox("Stato", ["TUTTI","Bozza","Inviata","Registrata","sent","received","accepted","rejected"])
    with col_btn_emesse:
        show_emesse = st.toggle("Emesse", value=True)
    with col_btn_ricevute:
        show_ricevute = st.toggle("Ricevute", value=True)
    with col_btn_agg:
        refresh = st.button("Aggiorna")

    # Mesi (solo estetico, nessun filtro per ora)
    mesi = [
        "Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno",
        "Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"
    ]
    tabs = st.tabs(mesi)
    idx_mese = date.today().month - 1

    with tabs[idx_mese]:
        frames = []

        # Fatture emesse: solo quelle create nella tua app
        if show_emesse and not st.session_state.documenti_emessi.empty:
            df_e = st.session_state.documenti_emessi.copy()
            df_e["Tipo"] = "Emessa"
            frames.append(df_e)

        # Fatture ricevute: SOLO lettura da Openapi (SdI)
        if show_ricevute:
            if not api_key:
                st.warning("Inserisci API Key Openapi nella sidebar per vedere le fatture ricevute da SdI.")
            else:
                df_r = get_fatture_ricevute(api_key)
                if not df_r.empty:
                    frames.append(df_r)

        if frames:
            df = pd.concat(frames, ignore_index=True)
            # Filtro testo
            if testo:
                mask = (
                    df["Numero"].astype(str).str.contains(testo, case=False, na=False) |
                    df.get("Cliente", df.get("Cliente/Fornitore",""))
                      .astype(str).str.contains(testo, case=False, na=False)
                )
                df = df[mask]
            # Filtro stato
            if stato != "TUTTI" and "Stato" in df.columns:
                df = df[df["Stato"] == stato]
            st.dataframe(df, use_container_width=True, height=450)
        else:
            st.info("Nessun documento da mostrare per i filtri selezionati.")

# ==== PAGINA CREA FATTURA (SOLO EMESSE, SENZA RICEVUTE) ====
elif pagina == "Crea fattura":
    st.subheader("Crea nuova fattura emessa")
    num = st.text_input("Numero", f"FT{date.today().strftime('%y%m%d')}-001")
    data_f = st.date_input("Data", date.today())
    cliente = st.text_input("Cliente")
    importo = st.number_input("Importo", min_value=0.0, value=0.0)
    stato = st.selectbox("Stato", ["Bozza","Inviata"])

    if st.button("Salva fattura emessa", type="primary"):
        nuova = pd.DataFrame({
            "Tipo":["Emessa"],
            "Numero":[num],
            "Data":[str(data_f)],
            "Cliente":[cliente],
            "Importo":[importo],
            "Stato":[stato]
        })
        st.session_state.documenti_emessi = pd.concat(
            [st.session_state.documenti_emessi, nuova], ignore_index=True
        )
        st.success("✅ Fattura emessa salvata (solo lato app, non SdI)")

# ==== PAGINA DASHBOARD ====
else:
    st.subheader("Dashboard")
    col1,col2,col3,col4 = st.columns(4)

    # Emesse (locali)
    df_e = st.session_state.documenti_emessi
    num_emesse = len(df_e)
    tot_emesse = df_e["Importo"].sum() if not df_e.empty else 0

    # Ricevute (da Openapi)
    if api_key:
        df_r = get_fatture_ricevute(api_key)
    else:
        df_r = pd.DataFrame()
    num_ricevute = len(df_r)
    tot_ricevute = df_r["Importo"].sum() if not df_r.empty else 0

    col1.metric("Fatture emesse (app)", num_emesse)
    col2.metric("Totale emesso", f"€{tot_emesse:.0f}")
    col3.metric("Fatture ricevute (SdI)", num_ricevute)
    col4.metric("Totale acquisti", f"€{tot_ricevute:.0f}")

st.markdown("---")
st.caption("Fisco Chiaro – Emesse gestite dall'app, Ricevute solo da SdI/Openapi (non creabili a mano)")
