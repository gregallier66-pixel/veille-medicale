# ============================================
# CONFIGURATION DES SPÉCIALITÉS
# ============================================

"""
Ce module définit les spécialités médicales disponibles dans l'application,
ainsi que leurs journaux associés et les termes MeSH utilisés pour PubMed.

Tu peux enrichir ce fichier à volonté.
"""

SPECIALITES = {
    "Cardiologie": {
        "journaux": [
            "Circulation",
            "European Heart Journal",
            "Journal of the American College of Cardiology",
            "Hypertension",
            "Heart"
        ],
        "mesh_terms": "Cardiology[MeSH Terms] OR Cardiovascular Diseases[MeSH Terms]"
    },

    "Gynécologie / Obstétrique": {
        "journaux": [
            "Obstetrics and Gynecology",
            "American Journal of Obstetrics and Gynecology",
            "BJOG",
            "Human Reproduction"
        ],
        "mesh_terms": "Gynecology[MeSH Terms] OR Obstetrics[MeSH Terms]"
    },

    "Neurologie": {
        "journaux": [
            "Neurology",
            "Brain",
            "Annals of Neurology",
            "Stroke"
        ],
        "mesh_terms": "Neurology[MeSH Terms] OR Nervous System Diseases[MeSH Terms]"
    },

    "Endocrinologie": {
        "journaux": [
            "Journal of Clinical Endocrinology & Metabolism",
            "Diabetes Care",
            "Diabetologia",
            "Thyroid"
        ],
        "mesh_terms": "Endocrinology[MeSH Terms] OR Endocrine System Diseases[MeSH Terms]"
    },

    "Pneumologie": {
        "journaux": [
            "American Journal of Respiratory and Critical Care Medicine",
            "Chest",
            "Thorax",
            "European Respiratory Journal"
        ],
        "mesh_terms": "Pulmonary Medicine[MeSH Terms] OR Respiratory Tract Diseases[MeSH Terms]"
    },

    "Oncologie": {
        "journaux": [
            "Journal of Clinical Oncology",
            "Cancer",
            "The Lancet Oncology",
            "Annals of Oncology"
        ],
        "mesh_terms": "Oncology[MeSH Terms] OR Neoplasms[MeSH Terms]"
    },

    "Néphrologie": {
        "journaux": [
            "Journal of the American Society of Nephrology",
            "Kidney International",
            "Nephrology Dialysis Transplantation"
        ],
        "mesh_terms": "Nephrology[MeSH Terms] OR Kidney Diseases[MeSH Terms]"
    },

    "Hématologie": {
        "journaux": [
            "Blood",
            "Haematologica",
            "Leukemia",
            "Journal of Thrombosis and Haemostasis"
        ],
        "mesh_terms": "Hematology[MeSH Terms] OR Hematologic Diseases[MeSH Terms]"
    }
}
```

**Structure de votre projet :**
```
votre-dossier/
├── app.py
├── config_specialites.py  ← créez ce fichier
├── utils_text.py (si séparé)
├── utils_traduction.py (si séparé)
└── requirements.txt
