# 📦 STOW AS Report – Dashboard

Interaktívny analytický dashboard pre STOW AS Report dáta zo SKLC3-Autostore.

## Funkcie

- **Celkový prehľad** – KPI karty (JBL, množstvo, doklady, produkty)
- **Rozdelenie podľa dokladu** – VGP, SP, VV, REP, SKL s detailmi
- **Operátori** – Top 15 bar chart, JBL vs množstvo, dominantný typ
- **Analýza množstva** – Distribúcia kusov, štatistiky podľa dokladu
- **Skladové sekcie** – Poschodia, top sekcie, doklad × poschodie
- **Produktová analýza** – Top produkty celkovo a podľa typu
- **Filtre** – Typ dokladu, operátor, poschodie
- **Export** – Stiahnutie filtrovaných dát ako CSV

## Spustenie lokálne

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy na Streamlit Cloud

1. Push tento repozitár na GitHub
2. Choď na [share.streamlit.io](https://share.streamlit.io)
3. Vyber repo → Main file: `app.py`
4. Deploy

## Dáta

Nahraj `STOW_AS_REPORT.xlsx` cez sidebar po spustení appky.
