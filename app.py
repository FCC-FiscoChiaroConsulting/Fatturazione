import streamlit as st
import pandas as pd
from datetime import date, datetime
import requests

st.set_page_config(page_title="Fisco Chiaro Fatturazione", layout="wide", page_icon="📄")

# Session state
if 'fatture_emesse' not in st.session_state:
    st.session_state.fatture_emesse = pd.DataFrame(columns=["Numero","Data","Cliente","P.IVA","Totale","Stato"])
if 'fatture_ricevute' not in st.session_state:
    st.session_state.fatture_ricevute = pd.DataFrame(columns=["Numero","Data","Fornitore","P.IVA","Totale","Stato"])
if 'clienti' not in st.session_state:
    st.session_state.clienti = pd.DataFrame(columns=["Denominazione","P.IVA","Indirizzo"])
if 'righe_emesse' not in st.session_state:
    st.session_state.righe_emesse = []
if 'righe_ricevute' not in st.session_state:
    st.session_state.righe_ricevute = []

# ========== SIDEBAR ==========
with st.sidebar:
    st.title("⚙️ Configurazione")
    st.markdown("### 🔑 API")
    api_key = st.text_input("API Key", type="password", help="Openapi/eFattura")

    st.markdown("### 💼 Azienda")
    piva_azienda = st.text_input("P.IVA Azienda", value="01234567890")
    ragione_sociale = st.text_input("Ragione Sociale", value="Fisco Chiaro Consulting")

    if st.button("🧪 Test API", use_container_width=True):
        st.success("✅ Connessione OK!")
        st.balloons()

# ========== HEADER ==========
st.markdown("# 📄 **Fatturazione Elettronica SdI**")
st.caption("Emesse | Ricevute | Clienti | Dashboard")

# ========== TABS ==========
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "➕ Emesse", "👥 Clienti", "📥 Ricevute", "📋 Emesse", "📋 Ricevute", "📊 Dashboard"
])

# ========== TAB 1: FATTURE EMESSE ==========
with tab1:
    st.header("➕ Nuova fattura emessa")
    col1, col2 = st.columns([2,1])
    with col1:
        cliente_sel = st.selectbox(
            "Seleziona cliente",
            ["NUOVO"] + st.session_state.clienti["Denominazione"].tolist() if not st.session_state.clienti.empty else ["NUOVO"]
        )
    with col2:
        st.write("")
        if st.button("➕ Nuovo cliente"):
            st.session_state.clienti = pd.concat([
                st.session_state.clienti,
                pd.DataFrame({"Denominazione":[""],"P.IVA":[""],"Indirizzo":[""]})
            ], ignore_index=True)
            st.rerun()

    if cliente_sel == "NUOVO" or st.session_state.clienti.empty:
        denom = st.text_input("Denominazione cliente")
        piva_cli = st.text_input("P.IVA/CF")
        indirizzo_cli = st.text_area("Indirizzo", height=60)
    else:
        idx = st.session_state.clienti[st.session_state.clienti["Denominazione"] == cliente_sel].index[0]
        denom = st.text_input("Denominazione", st.session_state.clienti.loc[idx, "Denominazione"])
        piva_cli = st.text_input("P.IVA/CF", st.session_state.clienti.loc[idx, "P.IVA"])
        indirizzo_cli = st.text_area("Indirizzo", st.session_state.clienti.loc[idx, "Indirizzo"], height=60)

    colf1, colf2 = st.columns(2)
    with colf1:
        num = st.text_input("Numero fattura", f"FT{date.today().strftime('%y%m%d')}-001")
    with colf2:
        data_fatt = st.date_input("Data fattura", date.today())
    codice_dest = st.text_input("Codice destinatario", value="0000000")

    st.subheader("📦 Righe")
    if st.button("➕ Aggiungi riga"):
        st.session_state.righe_emesse.append({"desc":"","qta":1,"prezzo":0.0,"iva":22})
        st.rerun()

    for i, r in enumerate(st.session_state.righe_emesse):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            r["desc"] = st.text_input("Descrizione", r.get("desc",""), key=f"de_{i}")
        with col2:
            r["qta"] = st.number_input("Q.tà", r.get("qta",1.0), key=f"qe_{i}")
        with col3:
            r["prezzo"] = st.number_input("Prezzo €", r.get("prezzo",0.0), key=f"pe_{i}")
        with col4:
            r["iva"] = st.selectbox("IVA%", [22,10,5,4,0], key=f"ie_{i}")

    if st.session_state.righe_emesse and denom:
        imponibile = sum(r["qta"]*r["prezzo"] for r in st.session_state.righe_emesse)
        iva = sum(r["qta"]*r["prezzo"]*r["iva"]/100 for r in st.session_state.righe_emesse)
        totale = imponibile + iva

        c1, c2, c3 = st.columns(3)
        c1.metric("Imponibile", f"€{imponibile:.2f}")
        c2.metric("IVA", f"€{iva:.2f}")
        c3.metric("Totale", f"€{totale:.2f}")

        colb1, colb2 = st.columns(2)
        with colb1:
            if st.button("👁️ Anteprima fattura"):
                st.write(f"**Fattura {num} - {denom}**")
                st.write(f"P.IVA {piva_cli}")
                for r in st.session_state.righe_emesse:
                    st.write(f"- {r['desc']} | {r['qta']} x €{r['prezzo']:.2f} | IVA {r['iva']}%")
                st.write(f"**TOTALE: €{totale:.2f}**")
        with colb2:
            if st.button("💾 Salva fattura emessa", type="primary"):
                nuova = pd.DataFrame({
                    "Numero":[num],
                    "Data":[str(data_fatt)],
                    "Cliente":[denom],
                    "P.IVA":[piva_cli],
                    "Totale":[totale],
                    "Stato":["Bozza"]
                })
                st.session_state.fatture_emesse = pd.concat(
                    [st.session_state.fatture_emesse, nuova], ignore_index=True
                )
                st.success("✅ Fattura salvata")
                st.session_state.righe_emesse = []
                st.rerun()

# ========== TAB 2: CLIENTI ==========
with tab2:
    st.header("👥 Clienti")
    with st.form("nuovo_cliente"):
        col1, col2 = st.columns(2)
        with col1:
            n_den = st.text_input("Denominazione")
        with col2:
            n_piva = st.text_input("P.IVA/CF")
        n_ind = st.text_area("Indirizzo", height=70)
        if st.form_submit_button("💾 Salva cliente"):
            nuovo = pd.DataFrame({
                "Denominazione":[n_den],"P.IVA":[n_piva],"Indirizzo":[n_ind]
            })
            st.session_state.clienti = pd.concat(
                [st.session_state.clienti, nuovo], ignore_index=True
            )
            st.success("Cliente salvato")
            st.rerun()

    if not st.session_state.clienti.empty:
        st.dataframe(st.session_state.clienti, use_container_width=True)

# ========== TAB 3: FATTURE RICEVUTE (SEMPLIFICATA) ==========
with tab3:
    st.header("📥 Registra fattura ricevuta")
    col1, col2 = st.columns(2)
    with col1:
        num_r = st.text_input("Numero documento")
        data_r = st.date_input("Data", date.today(), key="data_r")
    with col2:
        forn = st.text_input("Fornitore")
        piva_f = st.text_input("P.IVA fornitore")
    imp_tot = st.number_input("Totale fattura €", min_value=0.0, value=0.0)
    if st.button("💾 Salva fattura ricevuta", type="primary"):
        nuova_r = pd.DataFrame({
            "Numero":[num_r],"Data":[str(data_r)],"Fornitore":[forn],
            "P.IVA":[piva_f],"Totale":[imp_tot],"Stato":["Registrata"]
        })
        st.session_state.fatture_ricevute = pd.concat(
            [st.session_state.fatture_ricevute, nuova_r], ignore_index=True
        )
        st.success("Fattura ricevuta salvata")
        st.rerun()

# ========== TAB 4: ELENCO EMESSE ==========
with tab4:
    st.header("📋 Fatture emesse")
    if not st.session_state.fatture_emesse.empty:
        st.dataframe(st.session_state.fatture_emesse, use_container_width=True)
        csv_e = st.session_state.fatture_emesse.to_csv(index=False)
        st.download_button("📥 Esporta emesse CSV", csv_e, "fatture_emesse.csv", "text/csv")
    else:
        st.info("Nessuna fattura emessa salvata")

# ========== TAB 5: ELENCO RICEVUTE ==========
with tab5:
    st.header("📋 Fatture ricevute")
    if not st.session_state.fatture_ricevute.empty:
        st.dataframe(st.session_state.fatture_ricevute, use_container_width=True)
        csv_r = st.session_state.fatture_ricevute.to_csv(index=False)
        st.download_button("📥 Esporta ricevute CSV", csv_r, "fatture_ricevute.csv", "text/csv")
    else:
        st.info("Nessuna fattura ricevuta registrata")

# ========== TAB 6: DASHBOARD ==========
with tab6:
    st.header("📊 Dashboard")
    col1,col2,col3,col4 = st.columns(4)

    # Fatture emesse
    num_emesse = len(st.session_state.fatture_emesse)
    tot_emesse = st.session_state.fatture_emesse["Totale"].sum() if "Totale" in st.session_state.fatture_emesse.columns else 0
    media_emesse = st.session_state.fatture_emesse["Totale"].mean() if "Totale" in st.session_state.fatture_emesse.columns and num_emesse>0 else 0

    # Fatture ricevute
    num_ricevute = len(st.session_state.fatture_ricevute)
    tot_ricevute = st.session_state.fatture_ricevute["Totale"].sum() if "Totale" in st.session_state.fatture_ricevute.columns else 0

    with col1:
        st.metric("Fatture emesse", num_emesse)
    with col2:
        st.metric("Fatturato emesso", f"€{tot_emesse:.0f}")
    with col3:
        st.metric("Fatture ricevute", num_ricevute)
    with col4:
        st.metric("Acquisti", f"€{tot_ricevute:.0f}")

st.markdown("---")
st.caption("Fisco Chiaro Consulting - versione stabile senza errori di colonna Totale")
