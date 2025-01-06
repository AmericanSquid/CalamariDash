const fs = require('fs');

class LogParser {
    static parseADIFLogs(logPath) {
        try {
            console.log('Reading log file from:', logPath);
            const logContent = fs.readFileSync(logPath, 'utf8');
            console.log('Log file content length:', logContent.length);
            console.log('First 200 characters:', logContent.substring(0, 200));
            
            const entries = logContent.split('<EOH>')[1]?.split('\n') || [];
            console.log('Number of entries found:', entries.length);
            
            let qsos = [];
            let multipliers = new Set();
            let bands = new Set();
            
            entries.forEach(entry => {
                if (!entry.trim()) return;
                const qso = this.parseQSOEntry(entry);
                if (qso) {
                    qsos.push(qso);
                    if (qso.multiplier) multipliers.add(qso.multiplier);
                    if (qso.band) bands.add(qso.band);
                }
            });
            
            return {
                qsos,
                multipliers: Array.from(multipliers).filter(Boolean),
                bands: Array.from(bands)
            };
        } catch (error) {
            console.log('Log file access details:', {
                exists: fs.existsSync(logPath),
                error: error.message
            });
            return { qsos: [], multipliers: [], bands: [] };
        }
    }

    static parseQSOEntry(entry) {
        const fields = {
            call: /<CALL:(\d+)>([^<]+)/,
            freq: /<FREQ:(\d+)>([^<]+)/,
            mode: /<MODE:(\d+)>([^<]+)/,
            date: /<QSO_DATE:(\d+)>([^<]+)/,
            time: /<TIME_OFF:(\d+)>([^<]+)/
        };

        const extracted = {};
        for (const [key, regex] of Object.entries(fields)) {
            const match = entry.match(regex);
            if (match) extracted[key] = match[2];
        }

        if (!extracted.call) return null;

        const freq = parseFloat(extracted.freq);
        let band = '20';  // Default band

        // Order matters - check from highest to lowest frequency
        if (freq >= 28.0) band = '10';
        else if (freq >= 21.0) band = '15';
        else if (freq >= 14.0) band = '20';
        else if (freq >= 7.0) band = '40';
        else if (freq >= 3.5) band = '80';
        else band = '160';

        const year = extracted.date?.substring(0, 4);
        const month = extracted.date?.substring(4, 6);
        const day = extracted.date?.substring(6, 8);
        const hour = extracted.time?.substring(0, 2) || '00';
        const minute = extracted.time?.substring(2, 4) || '00';
        
        const timestamp = new Date(Date.UTC(year, month - 1, day, hour, minute));

        return {
            call: extracted.call,
            points: 1,
            timestamp,
            band,
            mode: extracted.mode || 'RTTY',
            frequency: freq
        };
    }
}

module.exports = LogParser;
