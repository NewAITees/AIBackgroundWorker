const { contextBridge, ipcRenderer } = require('electron');

/**
 * レンダラープロセスに安全なAPIを公開
 */
contextBridge.exposeInMainWorld('electronAPI', {
  // 設定関連
  getSettings: () => ipcRenderer.invoke('get-settings'),
  saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),

  // 通知関連
  showNotification: (title, body) => ipcRenderer.invoke('show-notification', { title, body }),

  // ウィンドウ制御
  minimizeToTray: () => ipcRenderer.invoke('minimize-to-tray'),

  // イベントリスナー
  onAutoRefresh: (callback) => {
    ipcRenderer.on('auto-refresh', callback);
  },
  onForceRefresh: (callback) => {
    ipcRenderer.on('force-refresh', callback);
  },
  onNavigateTo: (callback) => {
    ipcRenderer.on('navigate-to', (event, page) => callback(page));
  },
  onThemeChanged: (callback) => {
    ipcRenderer.on('theme-changed', (event, theme) => callback(theme));
  },

  // イベントリスナーの削除
  removeAutoRefreshListener: (callback) => {
    ipcRenderer.removeListener('auto-refresh', callback);
  },
  removeForceRefreshListener: (callback) => {
    ipcRenderer.removeListener('force-refresh', callback);
  },
  removeNavigateToListener: (callback) => {
    ipcRenderer.removeListener('navigate-to', callback);
  },
  removeThemeChangedListener: (callback) => {
    ipcRenderer.removeListener('theme-changed', callback);
  }
});
