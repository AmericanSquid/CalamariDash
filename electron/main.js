const { app, BrowserWindow, ipcMain } = require('electron');
const fs = require('fs');
const LogParser = require('../src/logParser');
const ScoreCalculator = require('../src/scoreCalculator');
const electronReload = require('electron-reload');
const path = require('path');

electronReload(path.join(__dirname, 'electron'), {
  verbose: true,
  onError: (err) => {
    console.error('Error with electron-reload:', err);
  }
});

let mainWindow;

app.on('ready', () => {
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'public', 'index.html'));
});

ipcMain.on('save-config', (event, config) => {
  const configPath = path.join(__dirname, 'config.json');
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  console.log('Configuration saved:', config);
  event.reply('config-saved', 'Configuration saved successfully!');
});

function loadConfig() {
  const configPath = path.join(__dirname, 'config.json');
  if (fs.existsSync(configPath)) {
    return JSON.parse(fs.readFileSync(configPath, 'utf8'));
  }
  return {};
}

const config = loadConfig();
const logPath = config.logPath || 'your/log/file/path.adif';

ipcMain.on('get-metrics', (event) => {
  try {
    const logData = LogParser.parseADIFLogs(logPath);
    console.log('Parsed logs:', logData);

    const qsos = logData.qsos || [];
    const multipliers = logData.multipliers || [];
    const totalScore = ScoreCalculator.calculateTotalScore(qsos, multipliers);
    const operatingTime = ScoreCalculator.calculateOperatingTime(qsos);
    const rate20 = ScoreCalculator.calculateRates(qsos, 20);
    const rate60 = ScoreCalculator.calculateRates(qsos, 60);

    const metrics = {
      totalQsos: qsos.length,
      multipliers: multipliers.length,
      totalScore,
      operatingTime,
      rate20,
      rate60,
      bands: logData.bands,
    };

    console.log('Metrics prepared:', metrics);
    event.reply('metrics-data', metrics);
  } catch (error) {
    console.error('Error generating metrics:', error.message);
    event.reply('metrics-data', { error: 'Failed to generate metrics.' });
  }
});
