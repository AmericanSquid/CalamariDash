const { ipcRenderer } = require('electron');

const saveConfigBtn = document.getElementById('saveConfigBtn');
const totalQsosElem = document.getElementById('totalQsos');
const totalMultipliersElem = document.getElementById('totalMultipliers');
const qsoRate20Elem = document.getElementById('qsoRate20');
const qsoRate60Elem = document.getElementById('qsoRate60');
const logList = document.getElementById('logList');

function debugLog(message) {
  console.log(`[DEBUG]: ${message}`);
}

debugLog('Requesting initial metrics...');
ipcRenderer.send('get-metrics');

ipcRenderer.on('metrics-data', (event, metrics) => {
  document.getElementById('totalQsos').textContent = metrics.totalQsos || '--';
  document.getElementById('totalMultipliers').textContent = metrics.multipliers || '--';
  document.getElementById('qsoRate20').textContent = metrics.qsoRate20 || '--';
  document.getElementById('qsoRate60').textContent = metrics.qsoRate60 || '--';
  console.log('Bands:', metrics.bands);


  if (metrics.logs) {
    logList.innerHTML = '';
    metrics.logs.forEach((log) => {
      const listItem = document.createElement('li');
      listItem.textContent = log;
      listItem.className = 'list-group-item';
      logList.appendChild(listItem);
    });
  }
});

saveConfigBtn.addEventListener('click', () => {
  const config = {
    name: document.getElementById('name').value,
    callsign: document.getElementById('callsign').value,
    contest: document.getElementById('contest').value,
  };

  debugLog(`Sending config to save: ${JSON.stringify(config)}`);
  ipcRenderer.send('save-config', config);
});

ipcRenderer.on('config-saved', (event, message) => {
  debugLog('Configuration saved confirmation received.');
  alert(message); // Notify user
});

setInterval(() => {
  debugLog('Requesting metrics update...');
  ipcRenderer.send('get-metrics');
}, 10000); // Every 10 seconds
