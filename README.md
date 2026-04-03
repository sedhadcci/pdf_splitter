# 📄 PDF Splitter

Outil Streamlit pour découper automatiquement un PDF multi-pages en fichiers individuels nommés.

## Fonctionnement

1. Dépose ton fichier PDF
2. L'app découpe chaque page et la renomme automatiquement
3. Télécharge un `.zip` contenant tous les PDFs

## Configuration des noms

Ouvre `app.py` et modifie le dictionnaire `PAGE_NAMES` :

```python
PAGE_NAMES = {
    1: "Seddik",
    2: "Arthur",
    3: "Rosana",
    4: "Axel",
}
```

## Lancer en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Déploiement sur Streamlit Cloud

1. Push le repo sur GitHub
2. Va sur [share.streamlit.io](https://share.streamlit.io)
3. Connecte ton repo et sélectionne `app.py`
4. C'est en ligne ✅
