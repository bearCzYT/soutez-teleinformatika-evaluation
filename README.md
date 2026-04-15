# soutez-teleinformatika-evaluation
Flask webová aplikace pro organizaci soutěžního hodnocení grafických prací. Umožňuje správu hodnoticích účtů, nahrávání prací, bodování podle kritérií a automatické vyhodnocení výsledků v jednotlivých kategoriích.
# 🏆 Hodnoticí systém pro soutěžní práce

Webová aplikace pro správu a hodnocení soutěžních prací v rámci školní soutěže.  
Systém umožňuje administrátorům spravovat uživatele, nahrávat práce a řídit průběh hodnocení. Hodnotitelé se mohou přihlásit pod vlastním účtem, bodově ohodnotit přidělené práce a po ukončení soutěže zobrazit výsledky.

## 📌 Co aplikace umí

- přihlášení přes login, heslo a identifikační klíč
- oddělené role **admin** a **hodnotitel**
- správa uživatelů a jejich oprávnění podle kategorií
- nahrávání soutěžních prací včetně náhledu a druhého obrázku
- nastavování stavu soutěže:
  - čekání
  - spuštěno
  - pozastaveno
  - ukončeno
- hodnocení prací podle definovaných kritérií
- evidence všech hodnocení
- přehled vlastních hodnocení
- hlášení nepřesností v hodnocení
- automatické vyhodnocení výsledků podle kategorií
- admin rozhraní pro kontrolu databáze a soutěžních dat

## 🛠️ Použité technologie

- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript

## 👥 Role v systému

### Admin
Admin má přístup ke správě celé soutěže. Může:
- přidávat, upravovat a mazat uživatele
- nastavovat oprávnění hodnotitelů
- nahrávat a mazat soutěžní práce
- měnit stav soutěže
- spravovat hodnoticí kritéria
- zobrazit všechna hodnocení
- zobrazit výsledky
- pracovat s databází

### Hodnotitel
Hodnotitel může:
- přihlásit se do systému
- hodnotit práce v kategoriích, ke kterým má oprávnění
- sledovat svůj postup hodnocení
- zobrazit svá předchozí hodnocení
- nahlásit chybu nebo nepřesnost v hodnocení
- po ukončení soutěže zobrazit výsledky

## 📂 Struktura projektu

```text
app.py
templates/
  admin.html
  admin_database.html
  admin_evaluations.html
  evaluate.html
  login.html
  my_evaluations.html
  results.html
  waiting.html
data/
uploads/
static/
