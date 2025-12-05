import streamlit as st
import pandas as pd
from datetime import date
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

PRIMARY_BLUE = "#1f77b4"

PDF_DIR = "fatture_pdf"
os.makedirs(PDF_DIR, exist_ok=True)

# ==========================
# STATO DI SESSIONE
# ==========================
COLONNE_DOC = ["Tipo", "Numero", "Data", "Cliente", "PIVA",
               "Importo", "Stato", "UUID", "PDF"]

if "documenti_emessi" not in st.session_state:
    st.session_state.documenti_emessi = pd.DataFrame(columns=COLONNE_DOC)

if "clienti" not in st.session_state:
    st.session_state.clienti = pd.DataFrame(
        columns=["Denominazione", "PIVA", "Indirizzo"]
    )

if "righe_correnti" not in st.session_state:
    st.session_state.righe_correnti = []

# ==========================
# SIDEBAR (STILE GESTIONALE)
# ==========================
with st.sidebar:
    st.markdown(
        f"<h2 style='color:{PRIMARY_BLUE}'>⚙️ Configurazione</h2>",
        unsafe_allow_html=True,
    )
    ambiente = st.selectbox(
        "Ambiente (placeholder)",
        ["Sandbox (test)", "Produzione"],
        index=0,
    )
    api_key = st.text_input(
        "API Key Openapi (non usata in questa versione)",
        type="password",
    )

    st.markdown("---")
    st.markdown("### 📑 Menu")

    pagina = st.radio(
        "",
        ["Lista documenti", "Crea fattura", "Clienti", "Dashboard"],
        label_visibility="collapsed",
    )

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
# FUNZIONE PDF
# ==========================


def genera_pdf_fattura(numero: str, data_f: date, cliente: dict,
                       righe: list, imponibile: float,
                       iva: float, totale: float) -> bytes:
    """Genera il PDF della fattura (senza simbolo € per evitare problemi di font)."""
    pdf = FPDF()
    pdf.add_page()

    # intestazione blu
    pdf.set_text_color(31, 119, 180)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "FISCO CHIARO CONSULTING", ln=1)
    pdf.set_text_color(0, 0, 0)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "Fattura emessa (uso interno / cliente)", ln=1)
    pdf.cell(0, 8, f"Numero: {numero}", ln=1)
    pdf.cell(0, 8, f"Data: {data_f.strftime('%d/%m/%Y')}", ln=1)
    pdf.ln(4)

    # cliente
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Cliente:", ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, cliente.get("Denominazione", "-"), ln=1)
    pdf.cell(0, 8, f"P.IVA/CF: {cliente.get('PIVA', '-')}", ln=1)
    if cliente.get("Indirizzo"):
        pdf.multi_cell(0, 6, cliente["Indirizzo"])
    pdf.ln(4)

    # righe
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Righe fattura:", ln=1)
    pdf.set_font("Helvetica", "", 10)
    for r in righe:
        desc = (r.get("desc") or "").replace("\n", " ")
        if len(desc) > 120:
            desc = desc[:117] + "..."
        riga_txt = (
            f"- {desc} | {r.get('qta', 0)} x "
            f"{r.get('prezzo', 0):.2f} (IVA {r.get('iva', 0)}%)"
        )
        pdf.multi_cell(0, 6, riga_txt)
    pdf.ln(4)

    # riepilogo
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Riepilogo:", ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(
        0,
        6,
        f"Imponibile: EUR {imponibile:,.2f}"
        .replace(",", "X").replace(".", ",").replace("X", "."),
        ln=1,
    )
    pdf.cell(
        0,
        6,
        f"IVA: EUR {iva:,.2f}"
        .replace(",", "X").replace(".", ",").replace("X", "."),
        ln=1,
    )
    pdf.cell(
        0,
        6,
        f"Totale: EUR {totale:,.2f}"
        .replace(",", "X").replace(".", ",").replace("X", "."),
        ln=1,
    )

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, "Documento generato dall'app Fisco Chiaro Consulting.")

    return pdf.output(dest="S").encode("latin-1")


# ==========================
# PAGINA 1: LISTA DOCUMENTI
# ==========================
if pagina == "Lista documenti":
    st.subheader("Lista documenti")

    col_cerca, col_stato, col_em, col_agg = st.columns([3, 2, 1, 1])
    with col_cerca:
        testo = st.text_input("Ricerca", placeholder="Numero, cliente...")
    with col_stato:
        stato_filtro = st.selectbox(
            "Stato",
            ["TUTTI", "Bozza", "Inviata", "Registrata"],
        )
    with col_em:
        show_emesse = st.toggle("Emesse", value=True)
    with col_agg:
        refresh = st.button("Aggiorna")

    mesi = [
        "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
    ]
    tabs = st.tabs(mesi)
    idx_mese = date.today().month - 1

    with tabs[idx_mese]:
        frames = []
        if show_emesse and not st.session_state.documenti_emessi.empty:
            frames.append(st.session_state.documenti_emessi.copy())

        if frames:
            df = pd.concat(frames, ignore_index=True)
            if testo:
                mask = (
                    df["Numero"].astype(str)
                    .str.contains(testo, case=False, na=False)
                    | df["Cliente"].astype(str)
                    .str.contains(testo, case=False, na=False)
                )
                df = df[mask]
            if stato_filtro != "TUTTI":
                df = df[df["Stato"] == stato_filtro]
            st.dataframe(
                df.drop(columns=["PDF"]),
                use_container_width=True,
                height=400,
            )
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
            scelta_num = st.selectbox(
                "Seleziona fattura emessa",
                numeri,
            )
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
                else:
                    st.warning("Il file PDF indicato non esiste più sul disco.")

# ==========================
# PAGINA 2: CREA FATTURA
# ==========================
elif pagina == "Crea fattura":
    st.subheader("Crea nuova fattura emessa")

    # selezione cliente
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
        cliente_corrente = {
            "Denominazione": cli_den,
            "PIVA": cli_piva,
            "Indirizzo": cli_ind,
        }
    else:
        riga_cli = st.session_state.clienti[
            st.session_state.clienti["Denominazione"] == cliente_sel
        ].iloc[0]
        cli_den = st.text_input("Denominazione", riga_cli["Denominazione"])
        cli_piva = st.text_input("P.IVA/CF", riga_cli["PIVA"])
        cli_ind = st.text_area("Indirizzo", riga_cli["Indirizzo"], height=60)
        cliente_corrente = {
            "Denominazione": cli_den,
            "PIVA": cli_piva,
            "Indirizzo": cli_ind,
        }

    coln1, coln2 = st.columns(2)
    with coln1:
        numero = st.text_input(
            "Numero fattura",
            f"FT{date.today().strftime('%y%m%d')}-001",
        )
    with coln2:
        data_f = st.date_input("Data fattura", date.today())

    st.markdown("### Righe fattura")

    if st.button("➕ Aggiungi riga"):
        st.session_state.righe_correnti.append(
            {"desc": "", "qta": 1.0, "prezzo": 0.0, "iva": 22}
        )
        st.rerun()

    imponibile = 0.0
    iva_tot = 0.0

    for i, r in enumerate(st.session_state.righe_correnti):
        c1, c2, c3, c4, c5 = st.columns([4, 1, 1, 1, 0.5])
        with c1:
            r["desc"] = st.text_input("Descrizione", r["desc"], key=f"desc_{i}")
        with c2:
            r["qta"] = st.number_input(
                "Q.tà", min_value=0.0, value=r["qta"], key=f"qta_{i}"
            )
        with c3:
            r["prezzo"] = st.number_input(
                "Prezzo", min_value=0.0, value=r["prezzo"], key=f"prz_{i}"
            )
        with c4:
            r["iva"] = st.selectbox(
                "IVA%",
                [22, 10, 5, 4, 0],
                index=[22, 10, 5, 4, 0].index(r["iva"]),
                key=f"iva_{i}",
            )
        with c5:
            if st.button("🗑️", key=f"del_{i}"):
                st.session_state.righe_correnti.pop(i)
                st.rerun()

        imp_riga = r["qta"] * r["prezzo"]
        iva_riga = imp_riga * r["iva"] / 100
        imponibile += imp_riga
        iva_tot += iva_riga

    totale = imponibile + iva_tot

    col_t1, col_t2, col_t3 = st.columns(3)
    col_t1.metric(
        "Imponibile",
        f"EUR {imponibile:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
    )
    col_t2.metric(
        "IVA",
        f"EUR {iva_tot:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
    )
    col_t3.metric(
        "Totale",
        f"EUR {totale:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
    )

    stato = st.selectbox("Stato", ["Bozza", "Inviata", "Registrata"])

    if st.button("💾 Salva fattura emessa", type="primary"):
        if not cliente_corrente["Denominazione"]:
            st.error("Inserisci almeno la denominazione del cliente.")
        elif not st.session_state.righe_correnti:
            st.error("Inserisci almeno una riga di fattura.")
        else:
            if cliente_sel == "NUOVO" and cliente_corrente["Denominazione"]:
                nuova_cli = pd.DataFrame([cliente_corrente])
                st.session_state.clienti = pd.concat(
                    [st.session_state.clienti, nuova_cli],
                    ignore_index=True,
                )

            pdf_bytes = genera_pdf_fattura(
                numero,
                data_f,
                cliente_corrente,
                st.session_state.righe_correnti,
                imponibile,
                iva_tot,
                totale,
            )
            pdf_filename = f"{numero.replace('/', '_')}.pdf"
            pdf_path = os.path.join(PDF_DIR, pdf_filename)
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)

            nuova = pd.DataFrame(
                [
                    {
                        "Tipo": "Emessa",
                        "Numero": numero,
                        "Data": str(data_f),
                        "Cliente": cliente_corrente["Denominazione"],
                        "PIVA": cliente_corrente["PIVA"],
                        "Importo": totale,
                        "Stato": stato,
                        "UUID": "",
                        "PDF": pdf_path,
                    }
                ],
                columns=COLONNE_DOC,
            )
            st.session_state.documenti_emessi = pd.concat(
                [st.session_state.documenti_emessi, nuova],
                ignore_index=True,
            )

            st.session_state.righe_correnti = []
            st.success("✅ Fattura emessa salvata e trasformata in PDF.")
            st.download_button(
                label="📥 Scarica subito il PDF",
                data=pdf_bytes,
                file_name=pdf_filename,
                mime="application/pdf",
            )

# ==========================
# PAGINA 3: CLIENTI
# ==========================
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
            nuovo = pd.DataFrame(
                [{"Denominazione": den, "PIVA": piva, "Indirizzo": ind}]
            )
            st.session_state.clienti = pd.concat(
                [st.session_state.clienti, nuovo],
                ignore_index=True,
            )
            st.success("Cliente salvato")

    if not st.session_state.clienti.empty:
        st.dataframe(st.session_state.clienti, use_container_width=True)
    else:
        st.info("Nessun cliente in rubrica.")

# ==========================
# PAGINA 4: DASHBOARD
# ==========================
else:
    st.subheader("Dashboard")
    df_e = st.session_state.documenti_emessi
    num_emesse = len(df_e)
    tot_emesse = df_e["Importo"].sum() if not df_e.empty else 0

    col1, col2 = st.columns(2)
    col1.metric("Fatture emesse (app)", num_emesse)
    col2.metric(
        "Totale emesso",
        f"EUR {tot_emesse:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
    )

st.markdown("---")
st.caption(
    "Fisco Chiaro Consulting – Emesse gestite dall'app; PDF generati automaticamente."
)
