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

The scoring profile interface is intentionally replaceable. The initial ARRL RTTY Roundup profile provides the HamDash-compatible metric pipeline; contest-specific exchange and multiplier rules should be refined against the contest's official rules before using it for an official score.

