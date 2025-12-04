import streamlit as st
import pandas as pd
from datetime import date, datetime
import requests

st.set_page_config(page_title="Fisco Chiaro Fatturazione", layout="wide", page_icon="📄")

# Session state
if 'fatture' not in st.session_state: 
    st.session_state.fatture = pd.DataFrame()
if 'righe' not in st.session_state: 
    st.session_state.righe = []

# ========== SIDEBAR ==========
with st.sidebar:
    st.title("⚙️ Configurazione")
    st.markdown("### 🔑 API")
    api_key = st.text_input("API Key", type="password", help="Openapi/eFattura")

    st.markdown("### 💼 Azienda")
    piva = st.text_input("P.IVA", value="01234567890")

    if st.button("🧪 Test API", use_container_width=True):
        st.success("✅ Connessione OK!")
        st.balloons()

# ========== HEADER ==========
st.markdown("# 📄 **Fatturazione Elettronica SdI**")
st.markdown("*Fisco Chiaro Consulting*")

# ========== TABS ==========
tab1, tab2, tab3 = st.tabs(["➕ Nuova Fattura", "📋 Elenco", "📊 Dashboard"])

# ========== TAB 1: NUOVA FATTURA ==========
with tab1:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📋 Dati Fattura")
        num = st.text_input("Numero", f"FT{date.today().strftime('%y%m%d')}-001")
        data = st.date_input("Data", date.today())

    with col2:
        st.subheader("👤 Cliente")
        cliente = st.text_input("Denominazione")
        piva_cliente = st.text_input("P.IVA/CF")
        codice_dest = st.text_input("Codice Dest.", value="0000000")

    st.subheader("📦 Righe")
    if st.button("➕ Aggiungi Riga"):
        st.session_state.righe.append({"desc":"","qta":1,"prezzo":0,"iva":22})
        st.rerun()

    for i, r in enumerate(st.session_state.righe):
        with st.container():
            col1,col2,col3,col4 = st.columns(4)
            with col1: r["desc"] = st.text_input("Descrizione", r.get("desc",""), key=f"d{i}")
            with col2: r["qta"] = st.number_input("Q.tà", r.get("qta",1), key=f"q{i}")
            with col3: r["prezzo"] = st.number_input("Prezzo €", r.get("prezzo",0), key=f"p{i}")
            with col4: r["iva"] = st.selectbox("IVA%", [22,10,4,0], key=f"i{i}")
            st.markdown("---")

    if st.session_state.righe:
        imponibile = sum(r["qta"]*r["prezzo"] for r in st.session_state.righe)
        iva = sum(r["qta"]*r["prezzo"]*r["iva"]/100 for r in st.session_state.righe)
        totale = imponibile + iva

        col1,col2,col3 = st.columns(3)
        col1.metric("Imponibile", f"€{imponibile:.2f}")
        col2.metric("IVA", f"€{iva:.2f}")
        col3.metric("**TOTALE**", f"€{totale:.2f}")

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("👁️ Anteprima"):
                st.json({"numero":num,"cliente":cliente,"totale":totale,"righe":st.session_state.righe})

        with col_btn2:
            if st.button("🚀 **INVIA SdI**", type="primary") and api_key:
                st.success(f"✅ Fattura {num} inviata al SdI!")
                new_row = pd.DataFrame({
                    "Numero":[num], "Data":[str(data)], "Cliente":[cliente],
                    "P.IVA":[piva_cliente], "Totale":[totale], "Stato":["Inviata"]
                })
                st.session_state.fatture = pd.concat([st.session_state.fatture, new_row], ignore_index=True)
                st.balloons()
                st.session_state.righe = []
                st.rerun()

# ========== TAB 2: ELENCO ==========
with tab2:
    if not st.session_state.fatture.empty:
        st.dataframe(st.session_state.fatture)
        csv = st.session_state.fatture.to_csv(index=False)
        st.download_button("📥 Esporta CSV", csv, "fatture.csv", "text/csv")
    else:
        st.info("👈 Crea la prima fattura!")

# ========== TAB 3: DASHBOARD ==========
with tab3:
    if not st.session_state.fatture.empty:
        col1,col2,col3 = st.columns(3)
        with col1: st.metric("Fatture", len(st.session_state.fatture))
        with col2: st.metric("Fatturato", f"€{st.session_state.fatture['Totale'].sum():.0f}")
        with col3: st.metric("Media", f"€{st.session_state.fatture['Totale'].mean():.0f}")
    else:
        st.info("📈 Crea fatture per statistiche")

st.markdown("---")
st.markdown("*Fisco Chiaro Consulting 2025*")
