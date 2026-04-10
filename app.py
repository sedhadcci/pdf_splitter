import streamlit as st
import pypdf
import fitz  # pymupdf
import zipfile
import io
import re

# ──────────────────────────────────────────────
#  CONFIGURATION
# ──────────────────────────────────────────────
# Hauteur (en %) de la zone du haut où chercher le nom
# 0.12 = 12% du haut de la page — ajuster si besoin
HEADER_ZONE_RATIO = 0.12
# ──────────────────────────────────────────────


def extract_name_from_page(fitz_doc, page_index: int) -> str:
    """Extrait le nom depuis la zone haute d'une page PDF."""
    page = fitz_doc[page_index]
    rect = page.rect

    top_zone = fitz.Rect(0, 0, rect.width, rect.height * HEADER_ZONE_RATIO)
    text = page.get_text("text", clip=top_zone).strip()

    for line in text.splitlines():
        line = line.strip()
        if line:
            clean = re.sub(r'[\\/*?:"<>|]', "", line)
            return clean

    return f"Page_{page_index + 1}"


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return name if name else "fichier_inconnu"


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

    # ── MODE DEBUG ──────────────────────────────
    with st.expander("🔍 Debug — voir tout le texte extrait par page"):
        st.caption(
            "Si 'PARIS Valerie' n'apparaît pas dans le texte extrait → "
            "le nom est une image → il faut activer l'OCR."
        )
        for i in range(num_pages):
            page = fitz_doc[i]
            rect = page.rect
            top_zone = fitz.Rect(0, 0, rect.width, rect.height * 0.30)
            raw_text = page.get_text("text", clip=top_zone).strip()
            st.markdown(f"**Page {i + 1} :**")
            st.code(raw_text if raw_text else "(aucun texte — probablement une image)")
    # ────────────────────────────────────────────

    st.divider()

    if st.button("🚀 Générer les PDFs", use_container_width=True, type="primary"):
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
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
                pdf_buffer.seek(0)

                zip_file.writestr(filename, pdf_buffer.read())

        zip_buffer.seek(0)

        st.download_button(
            label="⬇️ Télécharger tous les PDFs (.zip)",
            data=zip_buffer,
            file_name="pdfs_split.zip",
            mime="application/zip",
            use_container_width=True,
        )
