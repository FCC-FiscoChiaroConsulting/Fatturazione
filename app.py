import streamlit as st
import pandas as pd
from datetime import date
import os
from fpdf import FPDF

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
        columns=["Denominazione", "PIVA", "Indirizzo", "Tipo"]  # Tipo: Cliente/Fornitore
    )

if "righe_correnti" not in st.session_state:
    st.session_state.righe_correnti = []

# ==========================
# FUNZIONE PDF (CORRETTA)
# ==========================


def genera_pdf_fattura(
    numero: str,
    data_f: date,
    cliente: dict,
    righe: list,
    imponibile: float,
    iva: float,
    totale: float,
) -> bytes:
    """Genera PDF semplice della fattura (senza simbolo €)."""
    pdf = FPDF()
    pdf.add_page()

    pdf.set_text_color(31, 119, 180)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "FISCO CHIARO CONSULTING", ln=1)
    pdf.set_text_color(0, 0, 0)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "Fattura emessa (uso interno / cliente)", ln=1)
    pdf.cell(0, 8, f"Numero: {numero}", ln=1)
    pdf.cell(0, 8, f"Data: {data_f.strftime('%d/%m/%Y')}", ln=1)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Cliente:", ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, cliente.get("Denominazione", "-"), ln=1)
    pdf.cell(0, 8, f"P.IVA/CF: {cliente.get('PIVA', '-')}", ln=1)
    if cliente.get("Indirizzo"):
        pdf.multi_cell(0, 6, cliente["Indirizzo"])
    pdf.ln(4)

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
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Riepilogo:", ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(
        0,
        6,
        f"Imponibile: EUR {imponibile:,.2f}".replace(",", "X")
        .replace(".", ",")
        .replace("X", "."),
        ln=1,
    )
    pdf.cell(
        0,
        6,
        f"IVA: EUR {iva:,.2f}".replace(",", "X")
        .replace(".", ",")
        .replace("X", "."),
        ln=1,
    )
    pdf.cell(
        0,
        6,
        f"Totale: EUR {totale:,.2f}".replace(",", "X")
        .replace(".", ",")
        .replace("X", "."),
        ln=1,
    )

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, "Documento generato dall'app Fisco Chiaro Consulting.")

    data = pdf.output(dest="S")  # bytearray/bytes
    return bytes(data)

# ==========================
# SIDEBAR (STILE EFFATTA)
# ==========================
with st.sidebar:
    st.markdown("### 📄 Documenti")
    pagina = st.radio(
        "",
        [
            "Lista documenti",
            "Crea nuova fattura",
            "Download (documenti inviati)",
            "Carica pacchetto AdE",
            "Rubrica",
            "Dashboard",
        ],
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
# BARRA FRONTALE TIPO EFFATTA
# ==========================
barra_ricerca = ""
tabs = None
idx_mese = date.today().month  # 1-12

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
        st.button("STATO")
    with col_emesse:
        st.button("EMESSE")
    with col_ricevute:
        st.button("RICEVUTE")
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
    idx_mese = date.today().month

# ==========================
# PAGINA: LISTA DOCUMENTI
# ==========================
if pagina == "Lista documenti":
    st.subheader("Lista documenti")

    if tabs is not None:
        with tabs[idx_mese]:
            df_e = st.session_state.documenti_emessi.copy()

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
                st.dataframe(
                    df_e.drop(columns=["PDF"]),
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
                else:
                    st.warning("Il file PDF indicato non esiste più sul disco.")

# ==========================
# PAGINA: CREA NUOVA FATTURA
# ==========================
elif pagina == "Crea nuova fattura":
    st.subheader("Crea nuova fattura emessa")

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
            if (
                cliente_sel == "NUOVO"
                and cliente_corrente["Denominazione"]
                and cliente_corrente["Denominazione"]
                not in st.session_state.clienti["Denominazione"].tolist()
            ):
                nuovo_cli = pd.DataFrame(
                    [
                        {
                            "Denominazione": cliente_corrente["Denominazione"],
                            "PIVA": cliente_corrente["PIVA"],
                            "Indirizzo": cliente_corrente["Indirizzo"],
                            "Tipo": "Cliente",
                        }
                    ]
                )
                st.session_state.clienti = pd.concat(
                    [st.session_state.clienti, nuovo_cli],
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
                        "Controparte": cliente_corrente["Denominazione"],
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
# PAGINE EXTRA (download / pacchetto AdE / rubrica / dashboard)
# ==========================
elif pagina == "Download (documenti inviati)":
    st.subheader("Download documenti inviati")
    st.info("Area placeholder: qui potrai elencare e scaricare i documenti inviati allo SdI.")

elif pagina == "Carica pacchetto AdE":
    st.subheader("Carica pacchetto AdE (ZIP da cassetto fiscale)")
    uploaded_zip = st.file_uploader(
        "Carica file ZIP (fatture + metadati)", type=["zip"]
    )
    if uploaded_zip:
        st.write("Nome file caricato:", uploaded_zip.name)
        st.info("Parsing del pacchetto non ancora implementato in questa versione.")

elif pagina == "Rubrica":
    st.subheader("Rubrica (Clienti / Fornitori)")

    colf1, colf2 = st.columns(2)
    with colf1:
        filtra_clienti = st.checkbox("Mostra clienti", value=True)
    with colf2:
        filtra_fornitori = st.checkbox("Mostra fornitori", value=True)

    with st.form("nuovo_contatto"):
        col1, col2, col3 = st.columns(3)
        with col1:
            den = st.text_input("Denominazione")
        with col2:
            piva = st.text_input("P.IVA/CF")
        with col3:
            tipo = st.selectbox("Tipo", ["Cliente", "Fornitore"])
        ind = st.text_area("Indirizzo", height=60)
        if st.form_submit_button("💾 Salva contatto"):
            nuovo = pd.DataFrame(
                [
                    {
                        "Denominazione": den,
                        "PIVA": piva,
                        "Indirizzo": ind,
                        "Tipo": tipo,
                    }
                ]
            )
            st.session_state.clienti = pd.concat(
                [st.session_state.clienti, nuovo],
                ignore_index=True,
            )
            st.success("Contatto salvato")

    df_c = st.session_state.clienti.copy()
    if not df_c.empty:
        mask = []
        for _, r in df_c.iterrows():
            if r["Tipo"] == "Cliente" and filtra_clienti:
                mask.append(True)
            elif r["Tipo"] == "Fornitore" and filtra_fornitori:
                mask.append(True)
            else:
                mask.append(False)
        df_c = df_c[pd.Series(mask)]
        st.dataframe(df_c, use_container_width=True)
    else:
        st.info("Nessun contatto in rubrica.")

else:  # Dashboard
    st.subheader("Dashboard")
    df_e = st.session_state.documenti_emessi
    num_emesse = len(df_e)
    tot_emesse = df_e["Importo"].sum() if not df_e.empty else 0.0

    col1, col2 = st.columns(2)
    col1.metric("Fatture emesse (app)", num_emesse)
    col2.metric(
        "Totale emesso",
        f"EUR {tot_emesse:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
    )

st.markdown("---")
st.caption(
    "Fisco Chiaro Consulting – Emesse gestite dall'app, PDF generati automaticamente."
)

  
