# CalamariDash

CalamariDash bridges the gap between Linux-based contest stations and HamDash's real-time scoring platform. Now Linux users can participate fully in club competition tracking alongside their Windows-based fellow contesters. 

## Current Status
This is an alpha release focusing on FLDigi integration. The score calculator feature is currently under development. Future releases will include full support for:
- FLDigi
- WSJT-X 
- CQRLog

## Features
- Real-time Metrics: Track your QSO counts, multipliers, QSO rate, and more, updated live as you log your contacts.
- Log File Parsing: Reads and parses your FLDigi ADIF log fiel..
- Score Calculation: Automatically calculate scores based on logged data, using the ScoreCalculator module.
- HamDash Integration: Support for Affirmatech's HamDash allows Linux users to complete alongside their friends.
- Electron-based Desktop App: A cross-platform, real-time desktop application built with Electron for easy access to live stats and logs.

## How It Works
CalamariDash monitors your logging application's ADIF file for changes. When new QSOs are detected, it:
1. Parses the ADIF data
2. Calculates scores and multipliers
3. Uploads results to HamDash
4. Provides real-time status updates

## Building and Running
1. Clone this repository
2. Copy `.env.example` to `.env` and configure settings
3. Install dependencies: `npm install`
4. To package the app for production: `npm run build`
5. To start the app in development mode: `npm start`
6. To run the app without the UI: `npm run dev`

## Requirements
- Node.js v16 or higher
- FLDigi with ADIF logging enabled
- HamDash API key

## License
MIT License

## Author
K3AYV - Matthew Wagner

## Special Thanks
A huge shoutout to Scott N3FJP and Chris KB3KCN for allowing me to utilize their API to expand HamDash support to Linux users. Their ongoing support of my amateur radio endeavors, whether through encouragement during contests or sharing their knowledge to help me improve my station, has been invaluable. They've been there since the beginning, and I deeply appreciate their contributions. 
