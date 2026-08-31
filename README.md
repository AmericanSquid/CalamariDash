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

Open http://127.0.0.1:5000. The service reads FLDigi and WSJT-X ADIF files and can read Wavelog's delta ADIF API. Wavelog access is read-only. Configure environment variables from `.env.example`; load them with your preferred environment tool.

For Wavelog, create a read-only API key and set `WAVELOG_URL` to the Wavelog base URL (include `/index.php` when your installation uses that path), plus `WAVELOG_API_KEY` and `WAVELOG_STATION_ID`. The app polls Wavelog for new contacts and stores only the last fetched ID in `WAVELOG_STATE_PATH`.

The scoring profile interface is intentionally replaceable. The initial ARRL RTTY Roundup profile provides the HamDash-compatible metric pipeline; contest-specific exchange and multiplier rules should be refined against the contest's official rules before using it for an official score.
