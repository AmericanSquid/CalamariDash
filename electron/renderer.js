const { ipcRenderer } = require('electron');

// Save configuration
document.getElementById('saveConfigBtn').addEventListener('click', () => {
  const name = document.getElementById('name').value;
  const callsign = document.getElementById('callsign').value;
  const contest = document.getElementById('contest').value;

  const config = { name, callsign, contest };
  ipcRenderer.send('save-config', config);
});

// Confirmation when saved
ipcRenderer.on('config-saved', (event, message) => {
  alert(message);
});
