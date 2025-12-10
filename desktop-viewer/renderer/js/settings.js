/**
 * 設定画面機能
 */

/**
 * 設定画面初期化
 */
document.addEventListener('DOMContentLoaded', async () => {
  // 設定フォームのイベントリスナーを設定
  const settingsForm = document.getElementById('settingsForm');
  if (settingsForm) {
    settingsForm.addEventListener('submit', handleSettingsSubmit);
  }

  // API接続テストボタン
  const testApiBtn = document.getElementById('testApiBtn');
  if (testApiBtn) {
    testApiBtn.addEventListener('click', handleApiTest);
  }

  // 設定ページが表示されたら設定を読み込み
  const settingsNav = document.querySelector('.nav-item[data-page="settings"]');
  if (settingsNav) {
    settingsNav.addEventListener('click', loadSettings);
  }
});

/**
 * 設定を読み込み
 */
async function loadSettings() {
  try {
    const settings = await window.electronAPI.getSettings();

    // フォームに値を設定
    document.getElementById('apiEndpoint').value = settings.apiEndpoint || 'http://localhost:8000';
    document.getElementById('updateInterval').value = Math.floor(settings.updateInterval / 1000) || 300;
    document.getElementById('notificationsEnabled').checked = settings.notificationsEnabled !== false;
    document.getElementById('startMinimized').checked = settings.startMinimized || false;
    document.getElementById('theme').value = settings.theme || 'system';
  } catch (error) {
    console.error('Failed to load settings:', error);
    showNotification('エラー', '設定の読み込みに失敗しました');
  }
}

/**
 * 設定フォーム送信処理
 */
async function handleSettingsSubmit(e) {
  e.preventDefault();

  try {
    // フォームから値を取得
    const apiEndpoint = document.getElementById('apiEndpoint').value.trim();
    const updateIntervalSeconds = parseInt(document.getElementById('updateInterval').value, 10);
    const notificationsEnabled = document.getElementById('notificationsEnabled').checked;
    const startMinimized = document.getElementById('startMinimized').checked;
    const theme = document.getElementById('theme').value;

    // バリデーション
    if (!apiEndpoint) {
      showNotification('エラー', 'APIエンドポイントを入力してください');
      return;
    }

    if (isNaN(updateIntervalSeconds) || updateIntervalSeconds < 60) {
      showNotification('エラー', '更新間隔は60秒以上にしてください');
      return;
    }

    // 設定を保存
    const settings = {
      apiEndpoint,
      updateInterval: updateIntervalSeconds * 1000, // ミリ秒に変換
      notificationsEnabled,
      startMinimized,
      theme
    };

    const result = await window.electronAPI.saveSettings(settings);

    if (result.success) {
      // APIクライアントの設定を更新
      if (window.api) {
        window.api.baseURL = apiEndpoint;
      }

      showNotification('成功', '設定を保存しました');

      // テーマが変更された場合、即座に反映
      applyTheme(theme);
    } else {
      showNotification('エラー', '設定の保存に失敗しました');
    }
  } catch (error) {
    console.error('Failed to save settings:', error);
    showNotification('エラー', '設定の保存中にエラーが発生しました');
  }
}

/**
 * API接続テスト
 */
async function handleApiTest(e) {
  e.preventDefault();

  const testBtn = document.getElementById('testApiBtn');
  const originalText = testBtn.textContent;
  testBtn.textContent = 'テスト中...';
  testBtn.disabled = true;

  try {
    // フォームからAPIエンドポイントを取得
    const apiEndpoint = document.getElementById('apiEndpoint').value.trim();

    if (!apiEndpoint) {
      showNotification('エラー', 'APIエンドポイントを入力してください');
      return;
    }

    // 一時的にAPIクライアントのエンドポイントを変更してテスト
    const originalBaseURL = window.api.baseURL;
    window.api.baseURL = apiEndpoint;

    const isConnected = await window.api.testConnection();

    // 元のエンドポイントに戻す
    window.api.baseURL = originalBaseURL;

    if (isConnected) {
      showNotification('成功', 'API接続テストに成功しました');
    } else {
      showNotification('エラー', 'API接続テストに失敗しました。エンドポイントを確認してください。');
    }
  } catch (error) {
    console.error('API test failed:', error);
    showNotification('エラー', `API接続テストに失敗しました: ${error.message}`);
  } finally {
    testBtn.textContent = originalText;
    testBtn.disabled = false;
  }
}

/**
 * 通知を表示
 */
function showNotification(title, message) {
  if (window.electronAPI && window.electronAPI.showNotification) {
    window.electronAPI.showNotification(title, message);
  } else {
    // フォールバック: コンソールに出力
    console.log(`${title}: ${message}`);
    alert(`${title}\n\n${message}`);
  }
}

/**
 * テーマを適用（dashboard.jsから複製）
 */
function applyTheme(theme) {
  if (theme === 'system') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
  } else {
    document.documentElement.setAttribute('data-theme', theme);
  }

  // テーマ切り替えボタンのアイコンを更新
  const icon = document.querySelector('#themeToggle .icon');
  if (icon) {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    icon.textContent = currentTheme === 'dark' ? '☀️' : '🌙';
  }
}
