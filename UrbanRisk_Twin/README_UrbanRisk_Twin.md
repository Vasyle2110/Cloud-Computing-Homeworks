# UrbanRisk Twin API

UrbanRisk Twin este un backend Flask pentru monitorizarea riscurilor urbane în municipiul Iași. Aplicația colectează date meteo și de calitate a aerului, le combină cu indicatori urbani locali și calculează scoruri de risc pentru caniculă, poluare, ploaie/inundație urbană și risc global.

Backend-ul poate fi rulat local sau în Google Cloud Run. Datele live pot fi salvate local, în Firestore și în Cloud Storage. Actualizarea automată a datelor se face prin Google Cloud Scheduler.

## Base URL local

```txt
http://127.0.0.1:5000
```

## Base URL Cloud Run

```txt
https://urbanrisk-backend-6yt7khubnq-ey.a.run.app
```

---

## 1. Health & status

### GET /

Verifică dacă API-ul rulează.

```http
GET /
```

### GET /health

Verifică starea aplicației.

```http
GET /health
```

### GET /ingest/status

Returnează statusul ultimei ingestii de date live.

```http
GET /ingest/status
```

Exemplu de răspuns:

```json
{
  "status": "completed",
  "updated_at": "2026-05-26T01:00:00+00:00",
  "zones_total": 12,
  "zones_updated": 12,
  "errors_count": 0
}
```

Acest endpoint este util pentru frontend. UI-ul poate verifica periodic `updated_at`, iar dacă valoarea se schimbă, poate afișa un toast/pop-up de tipul: „Datele au fost actualizate”.

---

## 2. Zones

### GET /zones

Returnează lista zonelor urbane monitorizate.

```http
GET /zones
```

Acest endpoint este folosit pentru date descriptive/statice despre zone: nume, coordonate, indicatori urbani și alte câmpuri de bază.

### GET /zones/{zone_id}

Returnează detalii pentru o singură zonă, inclusiv scorurile de risc calculate pe baza celor mai recente date salvate.

```http
GET /zones/copou_01
```

Exemple de `zone_id`:

```txt
copou_01
tatarasi_01
centru_01
podu_ros_01
nicolina_01
pacurari_01
alexandru_01
cug_01
dacia_01
galata_01
bucium_01
frumoasa_01
```

### GET /zones/{zone_id}?date=YYYY-MM-DD&hour=HH

Returnează detaliile unei zone pentru o oră prognozată.

```http
GET /zones/centru_01?date=2026-05-26&hour=14
```

Parametri:

```txt
date = data în format YYYY-MM-DD
hour = ora fixă, între 0 și 23
```

Ora este interpretată în timezone-ul local:

```txt
Europe/Bucharest
```

Dacă parametrii `date` și `hour` nu sunt trimiși, endpoint-ul folosește datele curente/latest salvate prin ultima ingestie.

Exemplu de răspuns:

```json
{
  "zone_id": "centru_01",
  "name": "Centru",
  "city": "Iași",
  "latitude": 47.1585,
  "longitude": 27.6014,
  "temperature": 27.2,
  "humidity": 42,
  "rainfall_mm": 0.0,
  "wind_speed": 20.5,
  "european_aqi": 34,
  "pm10": 4.8,
  "pm2_5": 3.7,
  "carbon_monoxide": 121.0,
  "nitrogen_dioxide": 0.8,
  "ozone": 85.0,
  "vegetation_index": 0.144,
  "urban_density": 0.5702,
  "heat_risk": 14,
  "flood_risk": 2,
  "pollution_risk": 34,
  "global_risk": 24,
  "heat_label": "Low",
  "flood_label": "Low",
  "pollution_label": "Medium",
  "global_label": "Low",
  "requested_forecast": {
    "date": "2026-05-26",
    "hour": 14,
    "time": "2026-05-26T14:00",
    "timezone": "Europe/Bucharest",
    "mode": "hourly_forecast"
  },
  "source_times": {
    "weather_time": "2026-05-26T14:00",
    "air_quality_time": "2026-05-26T14:00"
  }
}
```

---

## 3. Risk endpoints

### GET /risk/global

Returnează toate zonele împreună cu scorurile calculate pe baza celor mai recente date live.

```http
GET /risk/global
```

Include:

```txt
heat_risk
flood_risk
pollution_risk
global_risk
heat_label
flood_label
pollution_label
global_label
dominant_risk_type
dominant_risk_score
```

Acesta este endpoint-ul recomandat pentru harta principală și pentru colorarea poligoanelor în UI.

### GET /risk/global?date=YYYY-MM-DD&hour=HH

Returnează toate zonele cu scorurile calculate pentru ora prognozată cerută.

```http
GET /risk/global?date=2026-05-26&hour=14
```

Acest endpoint folosește forecast-ul orar salvat prin:

```txt
Open-Meteo Forecast API
Open-Meteo Air Quality API
```

Dacă `date/hour` există în forecast-ul salvat, backend-ul suprascrie temporar valorile curente ale zonei cu valorile de la ora cerută și recalculează riscurile.

Dacă ora cerută nu există în datele salvate, endpoint-ul returnează eroare `400`.

### GET /risk/heat

Returnează riscul de caniculă pentru toate zonele.

```http
GET /risk/heat
```

### GET /risk/flood

Returnează riscul de ploaie/inundație urbană pentru toate zonele.

```http
GET /risk/flood
```

### GET /risk/pollution

Returnează riscul de poluare pentru toate zonele.

```http
GET /risk/pollution
```

---

## 4. Data ingestion

### POST /ingest/live-data

Rulează ingestia de date live și forecast.

```http
POST /ingest/live-data
```

Endpoint-ul colectează date din:

```txt
Open-Meteo Forecast API
Open-Meteo Air Quality API
Local urban baseline
```

Datele salvate includ valori curente:

```txt
temperature
humidity
rainfall_mm
wind_speed
european_aqi
pm10
pm2_5
carbon_monoxide
nitrogen_dioxide
ozone
```

și forecast pe ore:

```txt
weather_hourly
air_quality_hourly
forecast_metadata
```

Forecast-ul salvat permite interogări de forma:

```http
GET /risk/global?date=2026-05-26&hour=14
GET /zones/centru_01?date=2026-05-26&hour=14
```

În cloud, ingestia este declanșată automat prin Google Cloud Scheduler.

Pentru demo, scheduler-ul poate fi setat la fiecare minut:

```txt
* * * * *
```

Pentru utilizare normală, se recomandă revenirea la rulare orară:

```txt
0 * * * *
```

---

## 5. Recommendations

### GET /recommendations/{zone_id}

Returnează recomandări pentru o zonă.

```http
GET /recommendations/copou_01
```

Recomandările sunt generate în funcție de scorurile de risc ale zonei.

---

## 6. Simulations

### POST /simulate/heatwave

Simulează o situație de caniculă pentru toate zonele.

```http
POST /simulate/heatwave
```

Body:

```json
{
  "temperature": 38,
  "humidity": 45
}
```

Parametri:

```txt
temperature = temperatura simulată în grade Celsius
humidity = umiditatea simulată, opțională
```

Răspunsul include scorul inițial, scorul simulat și diferența pentru fiecare zonă.

### POST /simulate/rainfall

Simulează un eveniment de ploaie pentru toate zonele.

```http
POST /simulate/rainfall
```

Body:

```json
{
  "rainfall_mm_per_hour": 10,
  "start_date": "2026-05-26",
  "start_hour": 14,
  "end_hour": 18
}
```

Variantă cu trecere peste miezul nopții:

```json
{
  "rainfall_mm_per_hour": 8,
  "start_date": "2026-05-26",
  "start_hour": 22,
  "end_date": "2026-05-27",
  "end_hour": 3
}
```

Parametri:

```txt
rainfall_mm_per_hour = cantitatea simulată de ploaie pe oră
start_date = data de început, format YYYY-MM-DD
start_hour = ora de început, între 0 și 23
end_date = data de final, opțională
end_hour = ora de final, între 0 și 23
```

Simularea construiește artificial un eveniment de ploaie și calculează riscul de inundație pentru fiecare oră din interval. Răspunsul include riscul maxim și un timeline pe ore.

Exemplu conceptual:

```txt
rainfall_mm_per_hour = 10
start_hour = 14
end_hour = 18
```

Înseamnă că între 14:00 și 18:00 plouă constant cu 10 mm/oră.

---

## 7. Processing

### POST /process-risks

Procesează riscurile pe baza datelor existente.

```http
POST /process-risks
```

Acest endpoint poate fi folosit pentru regenerarea datelor procesate, dacă există flux separat de procesare.

---

## 8. Risk model summary

### Heat risk

Riscul de caniculă este calculat din:

```txt
temperature
humidity
vegetation_index
urban_density
```

Temperatura și umiditatea formează hazardul meteo, iar lipsa vegetației și densitatea urbană amplifică riscul.

Formula este construită astfel încât vegetația redusă și densitatea urbană să nu creeze singure risc de caniculă, ci să amplifice efectul temperaturii și al umidității.

### Pollution risk

Riscul de poluare este calculat în principal din:

```txt
air_quality_index / european_aqi
```

Factorii locali precum:

```txt
urban_density
vegetation_index
```

sunt folosiți doar ca amplificatori.

`traffic_level` nu este folosit în formula actuală, deoarece este o valoare baseline/manuală și poate distorsiona scorul.

### Flood risk

Riscul de inundație este calculat ca scor de risc pluvial urban, nu ca predicție hidrologică oficială.

Modelul analizează:

```txt
ploaia din ora selectată
ploaia acumulată în orele anterioare
ploaia prognozată imediat după ora selectată
durata evenimentului de ploaie
vegetation_index
urban_density
```

`drainage_quality` nu este folosit în formula actuală, deoarece este o valoare baseline/manuală.

Pentru interpretare:

```txt
1 mm de ploaie = 1 litru de apă pe metru pătrat
10 mm/oră = ploaie puternică
20 mm/oră = ploaie foarte serioasă pentru un mediu urban
```

Modelul ia în calcul atât ploile scurte și intense, cât și ploile mai slabe, dar persistente pe mai multe ore.

### Global risk

Riscul global combină:

```txt
heat_risk
flood_risk
pollution_risk
```

Scorul global este un indicator sintetic. Nu reprezintă o măsurătoare directă, ci o agregare a celor trei riscuri principale.

Pentru a nu ascunde un risc individual mare, modelul poate include și:

```txt
dominant_risk_type
dominant_risk_score
```

Exemplu:

```json
{
  "dominant_risk_type": "pollution",
  "dominant_risk_score": 42
}
```

---

## 9. Feature pipeline

Indicatorii urbani statici pot fi generați local prin scripturi auxiliare aflate în:

```txt
tools/flood_feature_builder/
```

Structura recomandată:

```txt
tools/flood_feature_builder/
├── data/
│   ├── vegetation_features.csv
│   └── urban_density_features.csv
├── scripts/
│   ├── build_vegetation_csv.py
│   ├── build_urban_density_csv.py
│   ├── sync_vegetation_to_base_zones.py
│   └── sync_urban_density_to_base_zones.py
└── .env
```

### vegetation_features.csv

Produce:

```txt
vegetation_index
```

Surse folosite:

```txt
OpenStreetMap
Sentinel-2 NDVI
ESA WorldCover
Copernicus CGLS
```

Interpretare:

```txt
0 = vegetație foarte redusă
1 = vegetație foarte ridicată
```

`vegetation_index` este un scor compozit, nu un procent exact de spațiu verde.

### urban_density_features.csv

Produce:

```txt
urban_density
```

Surse folosite:

```txt
OpenStreetMap buildings and roads
ESA WorldCover built-up
GHSL built surface
```

Interpretare:

```txt
0 = zonă slab construită / rar urbanizată
1 = zonă foarte construită / dens urbanizată
```

`urban_density` nu reprezintă densitatea populației. Este un indicator al suprafeței construite și al intensității urbane.

---

## 10. Deployment

Deploy pe Cloud Run:

```powershell
cd C:\Users\Loq\Desktop\UrbanRisk_Twin

$PROJECT_ID="powerful-decker-477422-h1"
$REGION="europe-west3"
$SERVICE_NAME="urbanrisk-backend"
$BUCKET_NAME="urbanrisk-twin-$PROJECT_ID"

gcloud config set project $PROJECT_ID

gcloud run deploy $SERVICE_NAME `
  --source . `
  --region $REGION `
  --allow-unauthenticated `
  --set-env-vars "PROJECT_ID=$PROJECT_ID,USE_FIRESTORE=true,USE_CLOUD_STORAGE=true,FIRESTORE_COLLECTION=urban_risk_zones,FIRESTORE_METADATA_COLLECTION=urban_risk_metadata,BUCKET_NAME=$BUCKET_NAME,CLOUD_STORAGE_PREFIX=urbanrisk-twin,DEBUG=false"
```

După deploy, este necesară o ingestie nouă:

```powershell
$CLOUD_RUN_URL = (gcloud run services describe $SERVICE_NAME `
  --region $REGION `
  --format="value(status.url)")

Invoke-RestMethod -Method POST "$CLOUD_RUN_URL/ingest/live-data"
```

Test endpoint global forecast:

```powershell
Invoke-RestMethod -Method GET "$CLOUD_RUN_URL/risk/global?date=2026-05-26&hour=14"
```

Test endpoint zonă forecast:

```powershell
Invoke-RestMethod -Method GET "$CLOUD_RUN_URL/zones/centru_01?date=2026-05-26&hour=14"
```

---

## 11. Google Cloud Scheduler

Jobul Scheduler apelează periodic endpoint-ul:

```http
POST /ingest/live-data
```

Verificare job:

```powershell
gcloud scheduler jobs describe urbanrisk-hourly-ingestion --location=europe-west3
```

Setare la fiecare minut pentru demo:

```powershell
gcloud scheduler jobs update http urbanrisk-hourly-ingestion `
  --location=europe-west3 `
  --schedule="* * * * *" `
  --time-zone="Europe/Bucharest"
```

Revenire la rulare orară:

```powershell
gcloud scheduler jobs update http urbanrisk-hourly-ingestion `
  --location=europe-west3 `
  --schedule="0 * * * *" `
  --time-zone="Europe/Bucharest"
```

Rulare manuală:

```powershell
gcloud scheduler jobs run urbanrisk-hourly-ingestion --location=europe-west3
```

---

## 12. Frontend integration notes

Pentru hartă și colorarea poligoanelor după risc, frontend-ul ar trebui să folosească:

```http
GET /risk/global
```

sau, pentru forecast pe oră:

```http
GET /risk/global?date=YYYY-MM-DD&hour=HH
```

Pentru detalii despre o singură zonă:

```http
GET /zones/{zone_id}
```

sau:

```http
GET /zones/{zone_id}?date=YYYY-MM-DD&hour=HH
```

Pentru notificare de actualizare date, frontend-ul poate verifica periodic:

```http
GET /ingest/status
```

Dacă `updated_at` se schimbă, UI-ul poate afișa un toast/pop-up și poate reîncărca datele de risc.

Flux recomandat UI:

```txt
1. UI citește /risk/global pentru harta inițială.
2. UI citește periodic /ingest/status.
3. Dacă updated_at s-a schimbat, afișează pop-up „Date actualizate”.
4. UI reapelează /risk/global.
5. Culorile poligoanelor se actualizează.
```

---

## 13. Important limitations

Acest proiect este un prototip academic / demonstrativ.

Limitări:

```txt
Nu reprezintă o prognoză oficială de inundații.
Nu folosește model hidrologic real.
Nu folosește date reale despre canalizare.
Nu folosește momentan poligoane oficiale de cartier.
Unele feature-uri sunt aproximări pe zone circulare.
Calitatea aerului vine din modele Open-Meteo/CAMS, nu din senzori locali de cartier.
```

Scorurile trebuie interpretate ca indicatori relativi de risc urban, nu ca predicții oficiale.
