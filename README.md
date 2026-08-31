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

For Wavelog, create a read-only API key, then enter the Wavelog base URL (include `/index.php` when your installation uses that path), API key, and station profile ID in **Settings**. The app polls Wavelog for new contacts and stores only its local fetch cursor.

The scoring profile interface is intentionally replaceable. The initial ARRL RTTY Roundup profile provides the HamDash-compatible metric pipeline; contest-specific exchange and multiplier rules should be refined against the contest's official rules before using it for an official score.
