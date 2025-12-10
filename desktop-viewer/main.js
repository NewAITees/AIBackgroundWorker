const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain, Notification } = require('electron');
const path = require('path');
const Store = require('electron-store');

// 設定ストア
const store = new Store({
  defaults: {
    apiEndpoint: 'http://localhost:8000',
    updateInterval: 300000, // 5分（ミリ秒）
    notificationsEnabled: true,
    startMinimized: false,
    theme: 'system' // 'light', 'dark', 'system'
  }
});

let mainWindow = null;
let tray = null;
let updateTimer = null;

/**
 * メインウィンドウを作成
 */
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 700,
    minWidth: 800,
    minHeight: 600,
    show: !store.get('startMinimized'),
    icon: path.join(__dirname, 'assets', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.loadFile('renderer/index.html');

  // ウィンドウを閉じる時、最小化してトレイに格納
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
    return false;
  });

  // ダークモードの変更を検知
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow.webContents.send('theme-changed', store.get('theme'));
  });
}

/**
 * システムトレイを作成
 */
function createTray() {
  // アイコンの作成（仮のアイコン、後で置き換え）
  const iconPath = path.join(__dirname, 'assets', 'icon.png');
  let trayIcon;

  try {
    trayIcon = nativeImage.createFromPath(iconPath);
    if (trayIcon.isEmpty()) {
      // アイコンが見つからない場合、空のアイコンを作成
      trayIcon = nativeImage.createEmpty();
    }
  } catch (error) {
    console.error('Failed to load tray icon:', error);
    trayIcon = nativeImage.createEmpty();
  }

  tray = new Tray(trayIcon);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'ダッシュボードを開く',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        } else {
          createWindow();
        }
      }
    },
    { type: 'separator' },
    {
      label: '今すぐ更新',
      click: () => {
        if (mainWindow) {
          mainWindow.webContents.send('force-refresh');
        }
        showNotification('更新中', 'データを更新しています...');
      }
    },
    { type: 'separator' },
    {
      label: '設定',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
          mainWindow.webContents.send('navigate-to', 'settings');
        }
      }
    },
    { type: 'separator' },
    {
      label: '終了',
      click: () => {
        app.isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setToolTip('AIBackgroundWorker Viewer');
  tray.setContextMenu(contextMenu);

  // トレイアイコンをダブルクリックで表示
  tray.on('double-click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
        mainWindow.focus();
      }
    }
  });
}

/**
 * 通知を表示
 */
function showNotification(title, body) {
  if (store.get('notificationsEnabled') && Notification.isSupported()) {
    new Notification({
      title: title,
      body: body,
      icon: path.join(__dirname, 'assets', 'icon.png')
    }).show();
  }
}

/**
 * 自動更新タイマーを開始
 */
function startUpdateTimer() {
  const interval = store.get('updateInterval');

  if (updateTimer) {
    clearInterval(updateTimer);
  }

  updateTimer = setInterval(() => {
    if (mainWindow) {
      mainWindow.webContents.send('auto-refresh');
    }
  }, interval);
}

/**
 * 自動更新タイマーを停止
 */
function stopUpdateTimer() {
  if (updateTimer) {
    clearInterval(updateTimer);
    updateTimer = null;
  }
}

// IPC通信のハンドラー
ipcMain.handle('get-settings', () => {
  return {
    apiEndpoint: store.get('apiEndpoint'),
    updateInterval: store.get('updateInterval'),
    notificationsEnabled: store.get('notificationsEnabled'),
    startMinimized: store.get('startMinimized'),
    theme: store.get('theme')
  };
});

ipcMain.handle('save-settings', (event, settings) => {
  store.set('apiEndpoint', settings.apiEndpoint);
  store.set('updateInterval', settings.updateInterval);
  store.set('notificationsEnabled', settings.notificationsEnabled);
  store.set('startMinimized', settings.startMinimized);
  store.set('theme', settings.theme);

  // 更新間隔が変更された場合、タイマーを再起動
  stopUpdateTimer();
  startUpdateTimer();

  // テーマが変更された場合、ウィンドウに通知
  if (mainWindow) {
    mainWindow.webContents.send('theme-changed', settings.theme);
  }

  return { success: true };
});

ipcMain.handle('show-notification', (event, { title, body }) => {
  showNotification(title, body);
  return { success: true };
});

ipcMain.handle('minimize-to-tray', () => {
  if (mainWindow) {
    mainWindow.hide();
  }
  return { success: true };
});

// アプリケーションの準備完了
app.whenReady().then(() => {
  createWindow();
  createTray();
  startUpdateTimer();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// すべてのウィンドウが閉じられた時
app.on('window-all-closed', () => {
  // macOS以外はアプリを終了しない（トレイに常駐）
  if (process.platform !== 'darwin') {
    // アプリを終了しない
  }
});

// アプリケーション終了前
app.on('before-quit', () => {
  app.isQuitting = true;
  stopUpdateTimer();
});

// アプリケーション終了
app.on('quit', () => {
  stopUpdateTimer();
});
