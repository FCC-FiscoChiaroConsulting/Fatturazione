import streamlit as st
import pandas as pd
from datetime import date
import requests

st.set_page_config(page_title="Fisco Chiaro - Fatture", layout="wide", page_icon="📄")

# ==== SIDEBAR CONFIG + MENU ====
with st.sidebar:
    st.markdown("### ⚙️ Configurazione")
    api_key = st.text_input("API Key Openapi", type="password")
    st.markdown("---")
    st.markdown("### 📑 Menu")
    pagina = st.radio("", ["Lista documenti","Crea fattura","Crea fattura ricevuta","Dashboard"], label_visibility="collapsed")

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

# ==== FUNZIONE CHIAMATA OPENAPI ====
@st.cache_data(ttl=60)
def get_fatture(type_value: int, api_key: str):
    if not api_key:
        return pd.DataFrame()
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"type": type_value}  # 0 = emesse, 1 = ricevute secondo doc Openapi
    try:
        r = requests.get(BASE_URL, headers=headers, params=params, timeout=15)
        if r.status_code != 200:
            st.error(f"Errore Openapi {r.status_code}: {r.text}")
            return pd.DataFrame()
        data = r.json()
        # adattamento minimo: prendo campi tipici (id, number, date, counterparty, total, status)
        rows = []
        for inv in data.get("data", data):  # alcuni account hanno lista direttamente
            rows.append({
                "ID": inv.get("id"),
                "Numero": inv.get("number"),
                "Data": inv.get("date"),
                "Controparte": inv.get("counterparty", {}).get("name"),
                "Partita IVA": inv.get("counterparty", {}).get("vatNumber"),
                "Totale": inv.get("totals", {}).get("grandTotal"),
                "Stato": inv.get("status")
            })
        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"Errore connessione Openapi: {e}")
        return pd.DataFrame()

# ==== PAGINA LISTA DOCUMENTI (EMESSE + RICEVUTE DA OPENAPI) ====
if pagina == "Lista documenti":
    st.subheader("Lista documenti da SdI (Openapi)")

    col_cerca, col_stato, col_btn_emesse, col_btn_ricevute, col_btn_agg = st.columns([3,2,1,1,1])
    with col_cerca:
        testo = st.text_input("Ricerca", placeholder="Numero, cliente, fornitore...")
    with col_stato:
        stato_f = st.selectbox("Stato", ["TUTTI","sent","received","accepted","rejected"])
    with col_btn_emesse:
        show_emesse = st.toggle("Emesse", value=True)
    with col_btn_ricevute:
        show_ricevute = st.toggle("Ricevute", value=True)
    with col_btn_agg:
        refresh = st.button("Aggiorna")

    if not api_key:
        st.warning("Inserisci API Key Openapi nella sidebar per vedere i dati SdI.")
    else:
        # carico emesse e/o ricevute da Openapi
        df_list = []
        if show_emesse:
            df_e = get_fatture(0, api_key)
            if not df_e.empty:
                df_e["Tipo"] = "Emessa"
                df_list.append(df_e)
        if show_ricevute:
            df_r = get_fatture(1, api_key)
            if not df_r.empty:
                df_r["Tipo"] = "Ricevuta"
                df_list.append(df_r)
        if df_list:
            df = pd.concat(df_list, ignore_index=True)
            # filtro testuale
            if testo:
                mask = (
                    df["Numero"].astype(str).str.contains(testo, case=False, na=False) |
                    df["Controparte"].astype(str).str.contains(testo, case=False, na=False) |
                    df["Partita IVA"].astype(str).str.contains(testo, case=False, na=False)
                )
                df = df[mask]
            # filtro stato
            if stato_f != "TUTTI" and "Stato" in df.columns:
                df = df[df["Stato"] == stato_f]
            st.dataframe(df, use_container_width=True, height=500)
        else:
            st.info("Nessun documento trovato su Openapi per i filtri selezionati.")

# ==== PAGINA CREA FATTURA (SOLO PLACEHOLDER, SENZA INVIO SDI) ====
elif pagina == "Crea fattura":
    st.subheader("Crea nuova fattura (bozza locale, non invia SdI)")
    st.info("Per l'invio reale verso SdI usa direttamente le API Openapi / il portale.")

# ==== PAGINA CREA FATTURA RICEVUTA (NOTE INTERNE) ====
elif pagina == "Crea fattura ricevuta":
    st.subheader("Annota manualmente una fattura ricevuta (extra rispetto a quelle SdI)")
    st.info("Le fatture passive ufficiali arrivano comunque dal canale SdI/Openapi e sono visibili in 'Lista documenti'.")

# ==== PAGINA DASHBOARD ====
else:
    st.subheader("Dashboard sintetica")
    if api_key:
        df_e = get_fatture(0, api_key)
        df_r = get_fatture(1, api_key)
        col1,col2,col3,col4 = st.columns(4)
        col1.metric("Emesse", len(df_e))
        col2.metric("Fatturato emesso", f"€{df_e['Totale'].sum():.0f}" if not df_e.empty else "€0")
        col3.metric("Ricevute", len(df_r))
        col4.metric("Acquisti", f"€{df_r['Totale'].sum():.0f}" if not df_r.empty else "€0")
    else:
        st.warning("Inserisci API Key Openapi per vedere le metriche reali da SdI.")
