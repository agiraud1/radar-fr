from datetime import date, timedelta

# MVP : petit jeu d'exemples. On branchera la vraie collecte ensuite.
def collect(limit: int = 8):
    base = date.today()
    sample = [
        {"text": "Ouverture d’une procédure de redressement judiciaire pour SOCIETE DURAND SAS (SIREN 512345678).",
         "url": "https://www.bodacc.fr/annonce/EXEMPLE1", "event_date": base.isoformat()},
        {"text": "Cession de fonds de commerce: BOULANGERIE MARTIN (SIREN 498765432) cède à GOURMANDISES SARL.",
         "url": "https://www.bodacc.fr/annonce/EXEMPLE2", "event_date": (base - timedelta(days=2)).isoformat()},
        {"text": "Augmentation de capital pour TECHNOVA SA (SIREN 732001234).",
         "url": "https://www.bodacc.fr/annonce/EXEMPLE3", "event_date": (base - timedelta(days=3)).isoformat()},
        {"text": "Transfert de siège social: LOGI-TRANS (SIREN 801223344) vers Lyon.",
         "url": "https://www.bodacc.fr/annonce/EXEMPLE4", "event_date": (base - timedelta(days=3)).isoformat()},
        {"text": "Plan de cession partielle pour METAINDUSTRIE SAS (SIREN 612009876).",
         "url": "https://www.bodacc.fr/annonce/EXEMPLE5", "event_date": (base - timedelta(days=4)).isoformat()},
        {"text": "Liquidation judiciaire simplifiée: ATELIER BOIS (SIREN 545667788).",
         "url": "https://www.bodacc.fr/annonce/EXEMPLE6", "event_date": (base - timedelta(days=5)).isoformat()},
        {"text": "Cession d’actifs non stratégiques par ALPHA AUTO (SIREN 512334455).",
         "url": "https://www.bodacc.fr/annonce/EXEMPLE7", "event_date": (base - timedelta(days=6)).isoformat()},
        {"text": "Projet de fusion: MEDICARE SAS (SIREN 523456789) absorbe BIOMEDIX.",
         "url": "https://www.bodacc.fr/annonce/EXEMPLE8", "event_date": (base - timedelta(days=7)).isoformat()},
    ]
    return sample[:limit]
