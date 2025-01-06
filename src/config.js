require('dotenv').config();

module.exports = {
    HAMDASH_API_URL: process.env.HAMDASH_API_URL,
    API_KEY: process.env.API_KEY,
    FLDIGI_LOG_PATH: process.env.FLDIGI_LOG_PATH,
    UPDATE_INTERVAL: 30000, // 30 seconds

    OPERATOR: {
        callsign: 'K3AYV',
        name: 'Matt'
    },

    CONTEST_CONFIG: {
        club: {
            name: 'Northeast Maryland Amateur Radio Contest Society'
        },
        software: 'FLDigi',
        softwareVersion: 'FLDigi via CalamariDigi',
        stationCategory: 'FIXED',
        bandCategory: 'ALL',
        modeCategory: 'SSB',
        assistedCategory: 'ASSISTED',
        transmittersCategory: 'ONE',
        powerCategory: 'HIGH',
        opsCategory: 'SINGLE-OP',
        overlayCategory: 'N/A',
    },

    STATION_INFO: {
        latitude: 39.3,
        longitude: -76.6,
        continent: 'NA',
        dxcc: 291,
        country: 'USA',
        state: 'MD',
        section: 'MDC',
        cqZone: 5,
        ituZone: 8
    }
};
