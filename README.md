# CalamariDash

Local Flask dashboard and HamDash standing uploader for amateur-radio contest stations.

## Run

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app calamaridash.app run --host 127.0.0.1
```

Open http://127.0.0.1:5000 and select **Settings** to configure the station, HamDash, log sources, and Wavelog without editing `.env`. Settings are saved locally in `calamaridash-settings.json`, which is excluded from Git. Environment values in `.env` remain useful as initial defaults.

The dashboard's **Start timer** and **Stop timer** buttons control operating time. Use **End contest** before changing the contest selector; ending clears the active local metrics so the next **Start timer** begins a new contest window. The contest selector uses common Cabrillo identifiers from the [WA7BNM Cabrillo-name list](https://www.contestcalendar.com/cabnames.php), and the custom field accepts any other Cabrillo name or code.

For Wavelog, create a read-only API key, then enter the Wavelog base URL (include `/index.php` when your installation uses that path), API key, and station profile ID in **Settings**. The app polls Wavelog for new contacts and stores only its local fetch cursor.

The scoring profile interface is intentionally replaceable. ARRL RTTY Roundup is currently the only exact contest profile: one point per valid callsign/band contact, with each US state/DC, Canadian province/territory, or non-US/non-Canadian DXCC entity counted once. Its score is QSO points multiplied by multipliers. Other contest selections remain available for HamDash telemetry, but are labeled **generic** until their official scoring profile is implemented.

For an edge-case contest, use the **Custom scoring profile** form in Settings. It supports fixed points per QSO, a multiplier field from the normalized QSO data, a duplicate policy, and either points-only or points-times-multipliers scoring. Saving the same contest code updates its local profile. Custom scores are labeled for verification and no user-entered expression is executed.
