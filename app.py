import streamlit as st
import pypdf
import fitz
import zipfile
import io
import re
import base64
import requests

# ──────────────────────────────────────────────
#  CONFIGURATION
# ──────────────────────────────────────────────
HEADER_ZONE_RATIO = 0.12

# CSS personnalisé
st.set_page_config(page_title="DRC - Rapports agents BI", page_icon="📊", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* Fond général */
.stApp {
    background: #f0f2f7;
}

/* Header principal */
.app-header {
    background: linear-gradient(135deg, #1a2b5e 0%, #2563eb 100%);
    border-radius: 16px;
    padding: 32px 36px;
    margin-bottom: 28px;
    color: white;
}
.app-header h1 {
    font-size: 1.7rem;
    font-weight: 600;
    margin: 0 0 4px 0;
    letter-spacing: -0.3px;
}
.app-header p {
    font-size: 0.9rem;
    opacity: 0.75;
    margin: 0;
}

/* Cards */
.card {
    background: white;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

/* Badge page */
.page-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid #f0f2f7;
}
.page-row:last-child { border-bottom: none; }
.page-badge {
    background: #eff6ff;
    color: #2563eb;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
    white-space: nowrap;
    font-family: 'DM Mono', monospace;
}
.page-name {
    font-size: 0.9rem;
    color: #1e293b;
    font-weight: 500;
}

/* Statut upload */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #ecfdf5;
    color: #065f46;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 500;
    margin-bottom: 20px;
}

/* Boutons */
div[data-testid="stButton"] > button {
    border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    height: 46px !important;
    transition: all 0.15s ease !important;
}

/* Séparateur */
hr { border-color: #e8eaf0 !important; margin: 24px 0 !important; }

/* File uploader */
[data-testid="stFileUploader"] {
    background: white;
    border-radius: 12px;
    padding: 8px;
}

/* Résultats envoi */
.result-ok {
    background: #ecfdf5;
    color: #065f46;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 0.85rem;
    margin: 4px 0;
}
.result-err {
    background: #fef2f2;
    color: #991b1b;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 0.85rem;
    margin: 4px 0;
}

/* Hide streamlit branding */
#MainMenu, footer { visibility: hidden; }
</style>

<div class="app-header">
    <h1>📊 DRC — Rapports agents BI</h1>
    <p>Importez votre rapport Power BI · Découpage automatique · Envoi vers SharePoint</p>
</div>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
#  FONCTIONS
# ──────────────────────────────────────────────
def extract_name_from_page(fitz_doc, page_index: int) -> str:
    page = fitz_doc[page_index]
    blocks = page.get_text("dict")["blocks"]
    best_text, best_size = "", 0
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = span.get("size", 0)
                text = span.get("text", "").strip()
                if text and size > best_size:
                    best_size = size
                    best_text = text
    if best_text:
        return re.sub(r'[\\/*?:"<>|]', "", best_text).strip()
    return f"Page_{page_index + 1}"


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return name if name else "fichier_inconnu"


def build_pdfs(reader, detected_names, num_pages) -> dict:
    pdfs, name_counts = {}, {}
    for i in range(num_pages):
        raw_name = sanitize_filename(detected_names[i])
        if raw_name in name_counts:
            name_counts[raw_name] += 1
            filename = f"{raw_name}_{name_counts[raw_name]}.pdf"
        else:
            name_counts[raw_name] = 1
            filename = f"{raw_name}.pdf"
        writer = pypdf.PdfWriter()
        writer.add_page(reader.pages[i])
        buf = io.BytesIO()
        writer.write(buf)
        pdfs[filename] = buf.getvalue()
    return pdfs


def send_to_sharepoint(pdfs: dict, pa_url_1: str, pa_url_2: str):
    """Envoie chaque PDF au flux 1, puis déclenche le flux 2 une seule fois après le dernier."""
    results = []
    filenames = list(pdfs.keys())

    for idx, filename in enumerate(filenames):
        payload = {
            "filename": filename,
            "content": base64.b64encode(pdfs[filename]).decode("utf-8")
        }
        try:
            r = requests.post(pa_url_1, json=payload, timeout=30)
            ok = r.status_code < 300
            results.append((filename, r.status_code, ok))
        except Exception as e:
            results.append((filename, str(e), False))

        # Dernier fichier → déclenche le flux 2
        if idx == len(filenames) - 1 and pa_url_2:
            try:
                requests.post(pa_url_2, json={"trigger": "all_files_sent"}, timeout=30)
            except Exception:
                pass

    return results


# ──────────────────────────────────────────────
#  INTERFACE
# ──────────────────────────────────────────────
uploaded_file = st.file_uploader("Déposer le fichier PDF Power BI", type="pdf", label_visibility="collapsed")

if uploaded_file:
    file_bytes = uploaded_file.read()
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    fitz_doc = fitz.open(stream=file_bytes, filetype="pdf")
    num_pages = len(reader.pages)

    detected_names = [extract_name_from_page(fitz_doc, i) for i in range(num_pages)]

    st.markdown(f"""
    <div class="status-pill">
        ✅ &nbsp; <strong>{num_pages} page(s)</strong> détectée(s) — {uploaded_file.name}
    </div>
    """, unsafe_allow_html=True)

    # Aperçu des pages
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("**📋 Fichiers qui seront générés**")
    for i, name in enumerate(detected_names):
        fname = sanitize_filename(name)
        st.markdown(f"""
        <div class="page-row">
            <span class="page-badge">Page {i+1}</span>
            <span class="page-name">{fname}.pdf</span>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()

    col1, col2 = st.columns(2)

    # Bouton ZIP
    with col1:
        if st.button("⬇️ Télécharger en ZIP", use_container_width=True):
            pdfs = build_pdfs(reader, detected_names, num_pages)
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for fname, fbytes in pdfs.items():
                    zf.writestr(fname, fbytes)
            zip_buffer.seek(0)
            st.download_button(
                label="📦 Cliquer pour télécharger",
                data=zip_buffer,
                file_name="rapports_agents.zip",
                mime="application/zip",
                use_container_width=True,
            )

    # Bouton SharePoint
    with col2:
        if st.button("📤 Envoyer vers SharePoint", use_container_width=True, type="primary"):
            try:
                pa_url_1 = st.secrets["POWER_AUTOMATE_URL"]
                pa_url_2 = st.secrets.get("POWER_AUTOMATE_URL_2", "")
            except Exception:
                st.error("❌ URLs Power Automate non configurées dans les secrets.")
                st.stop()

            pdfs = build_pdfs(reader, detected_names, num_pages)

            with st.spinner(f"Envoi de {len(pdfs)} fichier(s) en cours..."):
                results = send_to_sharepoint(pdfs, pa_url_1, pa_url_2)

            all_ok = all(ok for _, _, ok in results)
            if all_ok:
                st.success(f"✅ {len(pdfs)} fichier(s) déposés dans SharePoint — flux d'envoi déclenché !")
            else:
                for fname, status, ok in results:
                    if ok:
                        st.markdown(f'<div class="result-ok">✅ {fname}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="result-err">❌ {fname} — {status}</div>', unsafe_allow_html=True)
