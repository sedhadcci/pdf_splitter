import streamlit as st
import pypdf
import fitz  # pymupdf
import zipfile
import io
import re
import base64
import requests

# ──────────────────────────────────────────────
#  CONFIGURATION
# ──────────────────────────────────────────────
HEADER_ZONE_RATIO = 0.12
# L'URL du flux Power Automate est stockée dans les secrets Streamlit
# → fichier .streamlit/secrets.toml en local
# → Settings > Secrets sur Streamlit Cloud
# ──────────────────────────────────────────────


def extract_name_from_page(fitz_doc, page_index: int) -> str:
    """Extrait le nom en trouvant le texte avec la plus grande police sur la page."""
    page = fitz_doc[page_index]
    blocks = page.get_text("dict")["blocks"]

    best_text = ""
    best_size = 0

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
    """Génère tous les PDFs et retourne un dict {filename: bytes}."""
    pdfs = {}
    name_counts = {}

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

        pdf_buffer = io.BytesIO()
        writer.write(pdf_buffer)
        pdfs[filename] = pdf_buffer.getvalue()

    return pdfs


def send_to_sharepoint(pdfs: dict, power_automate_url: str):
    """Envoie chaque PDF au flux Power Automate."""
    results = []
    for filename, pdf_bytes in pdfs.items():
        payload = {
            "filename": filename,
            "content": base64.b64encode(pdf_bytes).decode("utf-8")
        }
        try:
            r = requests.post(power_automate_url, json=payload, timeout=30)
            results.append((filename, r.status_code, r.status_code < 300))
        except Exception as e:
            results.append((filename, str(e), False))
    return results


# ──────────────────────────────────────────────
#  INTERFACE
# ──────────────────────────────────────────────
st.set_page_config(page_title="PDF Splitter", page_icon="📄")

st.title("📄 PDF Splitter — Détection automatique")
st.markdown(
    "Dépose ton PDF : le nom en haut de chaque page sera détecté automatiquement "
    "et utilisé pour nommer le fichier généré."
)

uploaded_file = st.file_uploader("Choisir un fichier PDF", type="pdf")

if uploaded_file:
    file_bytes = uploaded_file.read()

    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    fitz_doc = fitz.open(stream=file_bytes, filetype="pdf")

    num_pages = len(reader.pages)
    st.success(f"✅ Fichier chargé : **{num_pages} page(s)** détectée(s)")

    detected_names = []
    for i in range(num_pages):
        name = extract_name_from_page(fitz_doc, i)
        detected_names.append(name)

    st.subheader("📋 Noms détectés")
    for i, name in enumerate(detected_names):
        col1, col2 = st.columns([1, 4])
        col1.markdown(f"**Page {i + 1}**")
        col2.markdown(f"`{sanitize_filename(name)}.pdf`")

    with st.expander("🔍 Debug — tailles de police détectées par page"):
        st.caption("Le texte avec la plus grande police est sélectionné comme nom.")
        for i in range(num_pages):
            page = fitz_doc[i]
            blocks = page.get_text("dict")["blocks"]
            sizes = []
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        t = span.get("text", "").strip()
                        s = span.get("size", 0)
                        if t:
                            sizes.append((round(s, 1), t[:60]))
            sizes.sort(reverse=True)
            st.markdown(f"**Page {i + 1} — top 5 textes par taille de police :**")
            st.table({"Taille": [x[0] for x in sizes[:5]], "Texte": [x[1] for x in sizes[:5]]})

    st.divider()

    col_dl, col_sp = st.columns(2)

    # ── Bouton téléchargement ZIP ──
    with col_dl:
        if st.button("🚀 Générer les PDFs", use_container_width=True, type="primary"):
            pdfs = build_pdfs(reader, detected_names, num_pages)

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for filename, pdf_bytes in pdfs.items():
                    zip_file.writestr(filename, pdf_bytes)
            zip_buffer.seek(0)

            st.download_button(
                label="⬇️ Télécharger tous les PDFs (.zip)",
                data=zip_buffer,
                file_name="pdfs_split.zip",
                mime="application/zip",
                use_container_width=True,
            )

    # ── Bouton envoi SharePoint ──
    with col_sp:
        if st.button("📤 Envoyer vers SharePoint", use_container_width=True):
            try:
                pa_url = st.secrets["POWER_AUTOMATE_URL"]
            except Exception:
                st.error("❌ URL Power Automate non configurée dans les secrets Streamlit.")
                st.stop()

            pdfs = build_pdfs(reader, detected_names, num_pages)

            with st.spinner(f"Envoi de {len(pdfs)} fichier(s) vers SharePoint..."):
                results = send_to_sharepoint(pdfs, pa_url)

            all_ok = all(ok for _, _, ok in results)

            if all_ok:
                st.success(f"✅ {len(pdfs)} fichier(s) déposés dans SharePoint avec succès !")
            else:
                for filename, status, ok in results:
                    if ok:
                        st.success(f"✅ {filename}")
                    else:
                        st.error(f"❌ {filename} — erreur : {status}")
