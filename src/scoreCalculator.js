class ScoreCalculator {
    static calculateRates(qsos, durationMinutes) {
        const now = new Date();
        const cutoff = new Date(now.getTime() - durationMinutes * 60000);
        return qsos.filter(qso => new Date(qso.timestamp) >= cutoff).length * (60 / durationMinutes);
    }

    static calculateTotalScore(qsos, multipliers) {
        return qsos.length * multipliers.length;
    }

    static calculateOperatingTime(qsos) {
        if (qsos.length < 2) return '00:00:00';
        const first = new Date(qsos[0].timestamp);
        const last = new Date(qsos[qsos.length - 1].timestamp);
        const diff = (last - first) / 1000;
        
        const hours = Math.floor(diff / 3600);
        const minutes = Math.floor((diff % 3600) / 60);
        const seconds = Math.floor(diff % 60);
        
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
}

module.exports = ScoreCalculator;
