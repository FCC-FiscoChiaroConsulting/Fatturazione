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
    "Importo",
    "TipoXML",  # codice XML (es. TD01)
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
    "Tipo",
]

if "documenti_emessi" not in st.session_state:
    st.session_state.documenti_emessi = pd.DataFrame(columns=COLONNE_DOC)
else:
    for col in COLONNE_DOC:
        if col not in st.session_state.documenti_emessi.columns:
            st.session_state.documenti_emessi[col] = (
                0.0 if col in ["Imponibile", "IVA", "Importo"] else ""
            )

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


def mostra_anteprima_pdf(pdf_bytes: bytes, altezza: int = 600) -> None:
    """Mostra un PDF inline come iframe tramite base64."""
    try:
        b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        pdf_display = f"""
        <iframe src="data:application/pdf;base64,{b64_pdf}"
                width="100%" height="{altezza}" type="application/pdf">
        </iframe>
        """
        st.markdown(pdf_display, unsafe_allow_html=True)
    except Exception as e:  # pragma: no cover
        st.warning(f"Impossibile mostrare l'anteprima PDF: {e}")


def get_next_invoice_number() -> str:
    """Restituisce il prossimo numero fattura del tipo FT{anno}{progressivo:03d}."""
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


def crea_riepilogo_fatture_emesse(df: pd.DataFrame) -> None:
    """Riepilogo per periodo: Importo a pagare / Imponibile / IVA."""
    if df.empty:
        st.info("Nessuna fattura emessa per creare il riepilogo.")
        return

    df = df.copy()
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    anni = sorted(df["Data"].dt.year.dropna().unique())
    if not anni:
        st.info("Nessuna data valida sulle fatture emesse.")
        return

    anno_default = date.today().year
    if anno_default not in anni:
        anno_default = anni[-1]
    idx_default = list(anni).index(anno_default)
    anno_sel = st.selectbox(
        "Anno", anni, index=idx_default, key="anno_riepilogo_emesse"
    )

    df_anno = df[df["Data"].dt.year == anno_sel]

    mesi_label = [
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

    rows = []

    # Mesi
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

    # Trimestri
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

    # Annuale
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
    st.dataframe(df_riep, use_container_width=True, hide_index=True)


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
    """PDF di cortesia semplice (senza simbolo €)."""
    pdf = FPDF()
    pdf.add_page()

    # Intestazione emittente
    pdf.set_text_color(31, 119, 180)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, EMITTENTE["Denominazione"], ln=1)
    pdf.set_text_color(0, 0, 0)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, EMITTENTE["Indirizzo"], ln=1)
    line2 = (
        f'{EMITTENTE["CAP"]} {EMITTENTE["Comune"]} ({EMITTENTE["Provincia"]}) IT'
    )
    pdf.cell(0, 5, line2, ln=1)
    pdf.cell(0, 5, f'CF {EMITTENTE["CF"]} - P.IVA {EMITTENTE["PIVA"]}', ln=1)
    pdf.ln(4)

    # Dati documento
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "FATTURA", ln=1)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, f"Numero: {numero}", ln=1)
    pdf.cell(0, 5, f"Data: {data_f.strftime("%d/%m/%Y")}", ln=1)
    pdf.ln(4)

    # Dati cliente
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Cliente", ln=1)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, cliente.get("Denominazione", "-"), ln=1)
    pdf.cell(0, 5, cliente.get("Indirizzo", ""), ln=1)
    line_cli2 = f"{cliente.get('CAP','')} {cliente.get('Comune','')} ({cliente.get('Provincia','')})"
    pdf.cell(0, 5, line_cli2, ln=1)
    if cliente.get("PIVA"):
        pdf.cell(0, 5, f"P.IVA: {cliente['PIVA']}", ln=1)
    if cliente.get("CF"):
        pdf.cell(0, 5, f"CF: {cliente['CF']}", ln=1)
    if cliente.get("CodiceDestinatario") or cliente.get("PEC"):
        pdf.cell(
            0,
            5,
            f"Codice Destinatario: {cliente.get('CodiceDestinatario','')}",
            ln=1,
        )
        if cliente.get("PEC"):
            pdf.cell(0, 5, f"PEC: {cliente['PEC']}", ln=1)
    pdf.ln(4)

    # Righe
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Righe fattura", ln=1)
    pdf.set_font("Helvetica", "", 9)

    for r in righe:
        desc = (r.get("desc") or "").replace("\n", " ").strip()
        if len(desc) > 120:
            desc = desc[:117] + "..."
        qta = r.get("qta", 0)
        prezzo = r.get("prezzo", 0.0)
        iva_perc = r.get("iva", 0)
        imp_riga = qta * prezzo
        riga_txt = (
            f"- {desc} | {qta} x {prezzo:.2f} "
            f"(IVA {iva_perc}% - imponibile {_format_val_eur(imp_riga)})"
        )
        pdf.multi_cell(0, 5, riga_txt)

    # Riepilogo importi
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Riepilogo importi", ln=1)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, f"Imponibile: EUR {_format_val_eur(imponibile)}", ln=1)
    pdf.cell(0, 5, f"IVA: EUR {_format_val_eur(iva)}", ln=1)
    pdf.cell(0, 5, f"Totale: EUR {_format_val_eur(totale)}", ln=1)

    # Pagamento
    if modalita_pagamento:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 5, "Modalità di pagamento:", ln=1)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, modalita_pagamento)

    # Note
    if note:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 5, "Note:", ln=1)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, note)

    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 7)
    pdf.multi_cell(
        0,
        4,
        "Documento generato dall'app Fisco Chiaro Consulting. "
        "Copia di cortesia senza valore fiscale.",
    )

    data_bytes = pdf.output(dest="S").encode("latin1")
    return data_bytes


# ==========================
# SIDEBAR / NAVIGAZIONE
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
# HEADER
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
# BARRA SUPERIORE (STATO/EMESSE/RICEVUTE)
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
    idx_mese = date.today().month


# ==========================
# LISTA DOCUMENTI
# ==========================
if pagina == "Lista documenti":
    st.subheader("Lista documenti")
    df_e_all = st.session_state.documenti_emessi.copy()

    if tabs is not None:
        # Tab Riepilogo (indice 0)
        with tabs[0]:
            crea_riepilogo_fatture_emesse(df_e_all)

        # Tab mese corrente (indice = mese)
        with tabs[idx_mese]:
            df_e = df_e_all.copy()

            if df_e.empty:
                st.info("Nessun documento emesso presente.")
            else:
                # parsing date + filtro mese
                df_e["Data"] = pd.to_datetime(df_e["Data"], errors="coerce")
                df_e = df_e[df_e["Data"].dt.month == idx_mese]

                # filtro ricerca
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

                if df_e.empty:
                    st.info("Nessun documento emesso per il mese selezionato.")
                else:
                    st.caption("Elenco fatture emesse (vista tipo Effatta)")
                    # ordino per data decrescente
                    df_e = df_e.sort_values("Data", ascending=False)

                    for _, row in df_e.iterrows():
                        row_index = row.name
                        data_doc = pd.to_datetime(row["Data"])
                        tipo_xml = row.get("TipoXML", "") or "TD01"
                        tipo_label = f"{tipo_xml} - FATTURA"

                        importo = float(row.get("Importo", 0.0) or 0.0)
                        controparte = row.get("Controparte", "")
                        stato_corrente = row.get("Stato", "Creazione") or "Creazione"
                        pdf_path = row.get("PDF", "")

                        with st.container():
                            st.markdown("---")
                            col_icon, col_info, col_imp, col_stato, col_menu = st.columns(
                                [0.6, 4, 1.4, 1.4, 1.8]
                            )

                            # ICONA PDF
                            with col_icon:
                                st.markdown("📄")

                            # INFO DOCUMENTO
                            with col_info:
                                st.markdown(
                                    f"**{tipo_label}**  \n"
                                    f"{row['Numero']} del {data_doc.strftime('%d/%m/%Y')}  \n"
                                    f"**INVIATO A**  \n"
                                    f"{controparte}"
                                )

                            # IMPORTO
                            with col_imp:
                                st.markdown("**IMPORTO (EUR)**")
                                st.markdown(_format_val_eur(importo))

                            # STATO
                            with col_stato:
                                st.markdown("**Stato**")
                                possibili_stati = ["Creazione", "Creato", "Inviato"]
                                if stato_corrente not in possibili_stati:
                                    stato_corrente = "Creazione"
                                new_stato = st.selectbox(
                                    "",
                                    possibili_stati,
                                    index=possibili_stati.index(stato_corrente),
                                    key=f"stato_{row_index}",
                                    label_visibility="collapsed",
                                )
                                st.session_state.documenti_emessi.loc[
                                    row_index, "Stato"
                                ] = new_stato

                            # MENU AZIONI
                            with col_menu:
                                st.markdown("**Azioni**")
                                azione = st.selectbox(
                                    "",
                                    [
                                        "-",
                                        "Visualizza",
                                        "Scarica pacchetto",
                                        "Scarica PDF fattura",
                                        "Scarica PDF proforma",
                                        "Modifica (placeholder)",
                                        "Duplica",
                                        "Elimina",
                                        "Invia (placeholder)",
                                    ],
                                    key=f"azione_{row_index}",
                                    label_visibility="collapsed",
                                )

                                if azione == "Visualizza":
                                    if pdf_path and os.path.exists(pdf_path):
                                        with open(pdf_path, "rb") as f:
                                            pdf_bytes = f.read()
                                        st.markdown("Anteprima PDF:")
                                        mostra_anteprima_pdf(pdf_bytes, altezza=400)
                                    else:
                                        st.warning("PDF non disponibile su disco.")

                                elif azione == "Scarica PDF fattura":
                                    if pdf_path and os.path.exists(pdf_path):
                                        with open(pdf_path, "rb") as f:
                                            pdf_bytes = f.read()
                                        st.download_button(
                                            "📥 Scarica PDF fattura",
                                            data=pdf_bytes,
                                            file_name=os.path.basename(pdf_path),
                                            mime="application/pdf",
                                            key=f"dl_{row_index}",
                                        )
                                    else:
                                        st.warning("PDF non disponibile su disco.")

                                elif azione == "Scarica pacchetto":
                                    st.info(
                                        "Funzione 'Scarica pacchetto' non ancora implementata."
                                    )

                                elif azione == "Scarica PDF proforma":
                                    st.info(
                                        "Funzione 'PDF proforma' non ancora implementata."
                                    )

                                elif azione == "Modifica (placeholder)":
                                    st.info(
                                        "Funzione modifica non ancora implementata in questa versione."
                                    )

                                elif azione == "Duplica":
                                    nuovo_num = get_next_invoice_number()
                                    nuova_riga = row.copy()
                                    nuova_riga["Numero"] = nuovo_num
                                    nuova_riga["Data"] = str(date.today())
                                    st.session_state.documenti_emessi = pd.concat(
                                        [
                                            st.session_state.documenti_emessi,
                                            pd.DataFrame([nuova_riga]),
                                        ],
                                        ignore_index=True,
                                    )
                                    st.success(f"Fattura duplicata come {nuovo_num}.")
                                    st.rerun()

                                elif azione == "Elimina":
                                    st.session_state.documenti_emessi = (
                                        st.session_state.documenti_emessi.drop(
                                            row_index
                                        ).reset_index(drop=True)
                                    )
                                    st.warning("Fattura eliminata.")
                                    st.rerun()

                                elif azione == "Invia (placeholder)":
                                    st.info(
                                        "Funzione invio a SdI non ancora implementata."
                                    )

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
# CREA NUOVA FATTURA
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
            index=default_idx,
        )
        st.session_state.cliente_corrente_label = cliente_sel

    with col2:
        if st.button("➕ Nuovo cliente"):
            st.session_state.cliente_corrente_label = "NUOVO"
            st.rerun()

    # Dati cliente
    if cliente_sel == "NUOVO":
        cli_den = st.text_input("Denominazione cliente")
        cli_piva = st.text_input("P.IVA")
        cli_cf = st.text_input("Codice Fiscale")
        cli_ind = st.text_input("Indirizzo (via/piazza, civico)")
        colc1, colc2, colc3 = st.columns(3)
        with colc1:
            cli_cap = st.text_input("CAP")
        with colc2:
            cli_com = st.text_input("Comune")
        with colc3:
            cli_prov = st.text_input("Provincia (es. BA)")
        colx1, colx2 = st.columns(2)
        with colx1:
            cli_cod_dest = st.text_input("Codice Destinatario", value="0000000")
        with colx2:
            cli_pec = st.text_input("PEC destinatario")
        cliente_corrente = {
            "Denominazione": cli_den,
            "PIVA": cli_piva,
            "CF": cli_cf,
            "Indirizzo": cli_ind,
            "CAP": cli_cap,
            "Comune": cli_com,
            "Provincia": cli_prov,
            "CodiceDestinatario": cli_cod_dest,
            "PEC": cli_pec,
        }
    else:
        riga_cli = st.session_state.clienti[
            st.session_state.clienti["Denominazione"] == cliente_sel
        ].iloc[0]
        cli_den = st.text_input("Denominazione", riga_cli.get("Denominazione", ""))
        cli_piva = st.text_input("P.IVA", riga_cli.get("PIVA", ""))
        cli_cf = st.text_input("Codice Fiscale", riga_cli.get("CF", ""))
        cli_ind = st.text_input(
            "Indirizzo (via/piazza, civico)", riga_cli.get("Indirizzo", "")
        )
        colc1, colc2, colc3 = st.columns(3)
        with colc1:
            cli_cap = st.text_input("CAP", riga_cli.get("CAP", ""))
        with colc2:
            cli_com = st.text_input("Comune", riga_cli.get("Comune", ""))
        with colc3:
            cli_prov = st.text_input(
                "Provincia (es. BA)", riga_cli.get("Provincia", "")
            )
        colx1, colx2 = st.columns(2)
        with colx1:
            cli_cod_dest = st.text_input(
                "Codice Destinatario", riga_cli.get("CodiceDestinatario", "0000000")
            )
        with colx2:
            cli_pec = st.text_input("PEC destinatario", riga_cli.get("PEC", ""))
        cliente_corrente = {
            "Denominazione": cli_den,
            "PIVA": cli_piva,
            "CF": cli_cf,
            "Indirizzo": cli_ind,
            "CAP": cli_cap,
            "Comune": cli_com,
            "Provincia": cli_prov,
            "CodiceDestinatario": cli_cod_dest,
            "PEC": cli_pec,
        }

    # Tipologia XML
    tipi_xml_label = [
        "TD01 - Fattura",
        "TD02 - Acconto/Anticipo su fattura",
        "TD04 - Nota di credito",
        "TD05 - Nota di debito",
    ]
    tipo_xml_label = st.selectbox("Tipo documento (XML)", tipi_xml_label, index=0)
    tipo_xml_codice = tipo_xml_label.split(" ")[0]

    coln1, coln2 = st.columns(2)
    with coln1:
        numero = st.text_input("Numero fattura", get_next_invoice_number())
    with coln2:
        data_f = st.date_input("Data fattura", date.today())

    modalita_pagamento = st.text_input(
        "Modalità di pagamento (es. Bonifico bancario su IBAN ...)",
        value="BONIFICO bancario su IBAN ................",
    )
    note = st.text_area("Note fattura (facoltative)", value="", height=80)

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
    col_t1.metric("Imponibile", f"EUR {_format_val_eur(imponibile)}")
    col_t2.metric("IVA", f"EUR {_format_val_eur(iva_tot)}")
    col_t3.metric("Totale", f"EUR {_format_val_eur(totale)}")

    stato = st.selectbox("Stato", ["Creazione", "Creato", "Inviato"])

    if st.button("💾 Salva fattura emessa", type="primary"):
        if not cliente_corrente["Denominazione"]:
            st.error("Inserisci almeno la denominazione del cliente.")
        elif not st.session_state.righe_correnti:
            st.error("Inserisci almeno una riga di fattura.")
        else:
            # salva/aggiorna cliente
            if (
                cliente_corrente["Denominazione"]
                and cliente_corrente["Denominazione"]
                not in st.session_state.clienti["Denominazione"].tolist()
            ):
                nuovo_cli = pd.DataFrame(
                    [
                        {
                            "Denominazione": cliente_corrente["Denominazione"],
                            "PIVA": cliente_corrente["PIVA"],
                            "CF": cliente_corrente["CF"],
                            "Indirizzo": cliente_corrente["Indirizzo"],
                            "CAP": cliente_corrente["CAP"],
                            "Comune": cliente_corrente["Comune"],
                            "Provincia": cliente_corrente["Provincia"],
                            "CodiceDestinatario": cliente_corrente[
                                "CodiceDestinatario"
                            ],
                            "PEC": cliente_corrente["PEC"],
                            "Tipo": "Cliente",
                        }
                    ]
                )
                st.session_state.clienti = pd.concat(
                    [st.session_state.clienti, nuovo_cli],
                    ignore_index=True,
                )
            else:
                mask = (
                    st.session_state.clienti["Denominazione"]
                    == cliente_corrente["Denominazione"]
                )
                for campo in [
                    "PIVA",
                    "CF",
                    "Indirizzo",
                    "CAP",
                    "Comune",
                    "Provincia",
                    "CodiceDestinatario",
                    "PEC",
                ]:
                    st.session_state.clienti.loc[mask, campo] = cliente_corrente[campo]

            # genera PDF
            pdf_bytes = genera_pdf_fattura(
                numero,
                data_f,
                cliente_corrente,
                st.session_state.righe_correnti,
                imponibile,
                iva_tot,
                totale,
                modalita_pagamento=modalita_pagamento,
                note=note,
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
                        "Imponibile": imponibile,
                        "IVA": iva_tot,
                        "Importo": totale,
                        "TipoXML": tipo_xml_codice,
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

            st.success("✅ Fattura emessa salvata e PDF generato.")
            st.download_button(
                label="📥 Scarica subito il PDF",
                data=pdf_bytes,
                file_name=pdf_filename,
                mime="application/pdf",
            )
            st.markdown("#### Anteprima PDF generato")
            mostra_anteprima_pdf(pdf_bytes, altezza=600)

# ==========================
# ALTRE PAGINE
# ==========================
elif pagina == "Download (documenti inviati)":
    st.subheader("Download documenti inviati")
    st.info(
        "Area placeholder: qui potrai elencare e scaricare i documenti inviati allo SdI."
    )

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
        col1, col2 = st.columns(2)
        with col1:
            den = st.text_input("Denominazione")
        with col2:
            piva = st.text_input("P.IVA")
        cf = st.text_input("Codice Fiscale")
        ind = st.text_input("Indirizzo (via/piazza, civico)")
        colc1, colc2, colc3 = st.columns(3)
        with colc1:
            cap = st.text_input("CAP")
        with colc2:
            com = st.text_input("Comune")
        with colc3:
            prov = st.text_input("Provincia (es. BA)")
        colx1, colx2 = st.columns(2)
        with colx1:
            cod_dest = st.text_input("Codice Destinatario", value="0000000")
        with colx2:
            pec = st.text_input("PEC destinatario")
        tipo = st.selectbox("Tipo", ["Cliente", "Fornitore"])
        if st.form_submit_button("💾 Salva contatto"):
            nuovo = pd.DataFrame(
                [
                    {
                        "Denominazione": den,
                        "PIVA": piva,
                        "CF": cf,
                        "Indirizzo": ind,
                        "CAP": cap,
                        "Comune": com,
                        "Provincia": prov,
                        "CodiceDestinatario": cod_dest,
                        "PEC": pec,
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

else:
    st.subheader("Dashboard")
    df_e = st.session_state.documenti_emessi
    num_emesse = len(df_e)
    tot_emesse = df_e["Importo"].sum() if not df_e.empty else 0.0
    col1, col2 = st.columns(2)
    col1.metric("Fatture emesse (app)", num_emesse)
    col2.metric("Totale emesso", f"EUR {_format_val_eur(tot_emesse)}")

st.markdown("---")
st.caption(
    "Fisco Chiaro Consulting – Emesse gestite dall'app, PDF generati automaticamente."
)
