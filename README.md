# CalamariDash

CalamariDash bridges the gap between Linux-based contest stations and HamDash's real-time scoring platform. Now Linux users can participate fully in club competition tracking alongside their Windows-based fellow contesters. 

## Current Status
This is an alpha release focusing on FLDigi integration. The score calculator feature is currently under development. Future releases will include full support for:
- FLDigi
- WSJT-X 
- CQRLog

## How It Works
CalamariDash monitors your logging application's ADIF file for changes. When new QSOs are detected, it:
1. Parses the ADIF data
2. Calculates scores and multipliers
3. Uploads results to HamDash
4. Provides real-time status updates

## Upcoming Features
- Graphical user interface for configuration and monitoring
- Live status display showing upload success/failures
- Real-time QSO rate tracking
- Easy configuration editing through UI
- Support for multiple logging applications
- Enhanced multiplier tracking

## Building and Running
1. Clone this repository
2. Copy `.env.example` to `.env` and configure settings
3. Install dependencies: `npm install`
4. Start tracking: `npm start` or `npm run dev`

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
