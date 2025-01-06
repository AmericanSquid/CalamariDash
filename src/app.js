const axios = require('axios');
const fs = require('fs');
const ora = require('ora');
const config = require('./config');
const LogParser = require('./logParser');
const ScoreCalculator = require('./scoreCalculator');

class HamDashUploader {
    constructor() {
        this.lastUpload = 0;
        this.spinner = ora('Monitoring FLDigi log file...');
    }

    async uploadScore(payload) {
        try {
            console.log('Sending payload to HamDash:', JSON.stringify(payload, null, 2));
            const response = await axios.post(config.HAMDASH_API_URL, payload, {
                headers: {
                    'apiKey': config.API_KEY,
                    'Content-Type': 'application/json',
                }
            });
            this.spinner.succeed('Upload successful!');
            console.log('HamDash Response:', response.data);
            return true;
        } catch (error) {
            this.spinner.fail('Upload failed');
            console.log('Full error details:', {
                status: error.response?.status,
                data: error.response?.data,
                message: error.message
            });
            return false;
        }
    }

    async processLogUpdate() {
        const now = Date.now();
        if (now - this.lastUpload < config.UPDATE_INTERVAL) {
            console.log('Waiting for update interval...');
            return;
        }
        
        console.log('Starting log processing...');
        this.spinner.start('Processing log update...');
        
        const { qsos, multipliers, bands } = LogParser.parseADIFLogs(config.FLDIGI_LOG_PATH);
        console.log(`Found ${qsos.length} QSOs, ${multipliers.length} multipliers`);
        
        if (!qsos.length) {
            console.log('No QSOs found in log');
            return;
        }

        console.log('Building payload...');
        const payload = this.buildPayload(qsos, multipliers, bands);
        
        console.log('Attempting upload to HamDash...');
        await this.uploadScore(payload);
        this.lastUpload = now;
    }

    buildPayload(qsos, multipliers, bands) {
        const totalQsos = qsos.length;
        const rate20 = ScoreCalculator.calculateRates(qsos, 20);
        const rate60 = ScoreCalculator.calculateRates(qsos, 60);
        const totalOpTime = ScoreCalculator.calculateOperatingTime(qsos);
        const avgQsHr = (totalQsos / (parseFloat(totalOpTime.split(':')[0]) || 1)).toFixed(1);
        
        const lastQso = qsos[qsos.length - 1];

        return {
            contest: 'TEST',
            score: ScoreCalculator.calculateTotalScore(qsos, multipliers),
            operator: {
                ...config.OPERATOR,
                band: lastQso.band || '20',
                mode: lastQso.mode || 'RTTY',
                rate20,
                rate60,
                frequency: lastQso.frequency
            },
            multiplierCount: multipliers.length,
            totalQsos,
            totalQsoPoints: qsos.reduce((sum, qso) => sum + qso.points, 0),
            ...config.CONTEST_CONFIG,
            ...config.STATION_INFO,
            totalOpTime,
            avgQsHr,
            firstQsoDate: qsos[0].timestamp.toISOString(),
            lastQso
        };
    }

    start() {
        this.spinner.start();
        fs.watch(config.FLDIGI_LOG_PATH, (eventType) => {
            if (eventType === 'change') {
                this.processLogUpdate();
            }
        });
    }
}

const uploader = new HamDashUploader();
uploader.start();
