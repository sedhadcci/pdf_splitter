import streamlit as st
import pypdf
import zipfile
import io

# ──────────────────────────────────────────────
#  CONFIGURATION — modifier ici si besoin
# ──────────────────────────────────────────────
PAGE_NAMES = {
    1: "Seddik",
    2: "Arthur",
    3: "Rosana",
    4: "Axel",
}
# ──────────────────────────────────────────────

st.set_page_config(page_title="PDF Splitter", page_icon="📄")

st.title("📄 PDF Splitter")
st.markdown("Dépose ton fichier PDF — chaque page sera automatiquement renommée et exportée.")

uploaded_file = st.file_uploader("Choisir un fichier PDF", type="pdf")

if uploaded_file:
    reader = pypdf.PdfReader(uploaded_file)
    num_pages = len(reader.pages)

    st.success(f"✅ Fichier chargé : **{num_pages} page(s)** détectée(s)")

    # Aperçu des fichiers qui seront générés
    st.subheader("📋 Fichiers qui seront générés")
    cols = st.columns(2)
    for i in range(1, num_pages + 1):
        name = PAGE_NAMES.get(i, f"Page_{i}")
        col = cols[(i - 1) % 2]
        col.markdown(f"**Page {i}** → `{name}.pdf`")

    if num_pages > len(PAGE_NAMES):
        st.warning(
            f"⚠️ Le PDF contient {num_pages} pages mais seulement {len(PAGE_NAMES)} noms sont configurés. "
            f"Les pages supplémentaires seront nommées `Page_X.pdf`."
        )

    st.divider()

    if st.button("🚀 Générer les PDFs", use_container_width=True, type="primary"):
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for i in range(num_pages):
                page_num = i + 1
                name = PAGE_NAMES.get(page_num, f"Page_{page_num}")

                writer = pypdf.PdfWriter()
                writer.add_page(reader.pages[i])

                pdf_buffer = io.BytesIO()
                writer.write(pdf_buffer)
                pdf_buffer.seek(0)

                zip_file.writestr(f"{name}.pdf", pdf_buffer.read())

        zip_buffer.seek(0)

        st.download_button(
            label="⬇️ Télécharger tous les PDFs (.zip)",
            data=zip_buffer,
            file_name="pdfs_split.zip",
            mime="application/zip",
            use_container_width=True,
        )
