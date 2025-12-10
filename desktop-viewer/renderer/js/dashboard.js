/**
 * ダッシュボード機能
 */

// グローバル変数
let currentPage = 'dashboard';
let lastUpdateTime = null;

/**
 * ページ初期化
 */
document.addEventListener('DOMContentLoaded', async () => {
  console.log('Dashboard initialized');

  // ナビゲーション設定
  setupNavigation();

  // ボタンイベント設定
  setupButtons();

  // テーマ設定
  setupTheme();

  // Electronイベントリスナー設定
  setupElectronListeners();

  // 初回データ読み込み
  await refreshData();
});

/**
 * ナビゲーション設定
 */
function setupNavigation() {
  const navItems = document.querySelectorAll('.nav-item');

  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const page = item.getAttribute('data-page');
      navigateTo(page);
    });
  });
}

/**
 * ページ遷移
 */
function navigateTo(page) {
  // ナビゲーションのアクティブ状態を更新
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.getAttribute('data-page') === page);
  });

  // ページの表示/非表示を切り替え
  document.querySelectorAll('.page').forEach(p => {
    p.classList.toggle('active', p.id === `${page}Page`);
  });

  // ページタイトルを更新
  const titles = {
    dashboard: 'ダッシュボード',
    lifelog: 'ライフログ',
    browser: 'ブラウザ履歴',
    news: 'ニュース',
    reports: 'レポート',
    settings: '設定'
  };
  document.getElementById('pageTitle').textContent = titles[page] || page;

  currentPage = page;

  // ページごとのデータを読み込み
  loadPageData(page);
}

/**
 * ページごとのデータを読み込み
 */
async function loadPageData(page) {
  try {
    switch (page) {
      case 'dashboard':
        await loadDashboard();
        break;
      case 'lifelog':
        await loadLifelog();
        break;
      case 'browser':
        await loadBrowser();
        break;
      case 'news':
        await loadNews();
        break;
      case 'reports':
        await loadReports();
        break;
    }
  } catch (error) {
    console.error(`Failed to load ${page} data:`, error);
    showError(`データの読み込みに失敗しました: ${error.message}`);
  }
}

/**
 * ダッシュボードデータを読み込み
 */
async function loadDashboard() {
  try {
    const data = await window.api.getDashboard();

    // ローディングを非表示
    document.querySelector('#dashboardPage .loading').style.display = 'none';

    // サマリーカードを表示
    const summaryGrid = document.querySelector('.summary-grid');
    if (summaryGrid) {
      summaryGrid.style.display = 'grid';

      // ライフログサマリー
      if (data.lifelog) {
        document.getElementById('activeTime').textContent = formatDuration(data.lifelog.active_duration || 0);
        document.getElementById('appCount').textContent = data.lifelog.app_count || 0;
      }

      // ブラウザ履歴サマリー
      if (data.browser) {
        document.getElementById('visitCount').textContent = data.browser.visit_count || 0;
        document.getElementById('browsingTime').textContent = formatDuration(data.browser.total_time || 0);
      }

      // 外部情報サマリー
      if (data.info) {
        document.getElementById('newsCount').textContent = data.info.news_count || 0;
        document.getElementById('reportCount').textContent = data.info.report_count || 0;
      }
    }

    // 最近のアクティビティを表示
    if (data.recent_activities) {
      renderTimeline(data.recent_activities);
    }

    // 最新ニュースを表示
    if (data.recent_news) {
      renderNews(data.recent_news);
    }

    updateLastUpdated();
  } catch (error) {
    console.error('Failed to load dashboard:', error);
    showError('ダッシュボードの読み込みに失敗しました');
  }
}

/**
 * ライフログデータを読み込み
 */
async function loadLifelog() {
  try {
    const summary = await window.api.getLifelogSummary();
    const content = document.getElementById('lifelogContent');

    let html = '<h4>今日の活動サマリー</h4>';
    html += `<p>アクティブ時間: ${formatDuration(summary.active_duration || 0)}</p>`;
    html += `<p>アイドル時間: ${formatDuration(summary.idle_duration || 0)}</p>`;
    html += `<p>使用アプリ数: ${summary.app_count || 0}</p>`;

    if (summary.top_apps && summary.top_apps.length > 0) {
      html += '<h4>よく使ったアプリ</h4><ul>';
      summary.top_apps.forEach(app => {
        html += `<li>${app.app_name}: ${formatDuration(app.duration)}</li>`;
      });
      html += '</ul>';
    }

    content.innerHTML = html;
  } catch (error) {
    console.error('Failed to load lifelog:', error);
    showError('ライフログの読み込みに失敗しました');
  }
}

/**
 * ブラウザ履歴を読み込み
 */
async function loadBrowser() {
  try {
    const history = await window.api.getBrowserHistory(50);
    const content = document.getElementById('browserContent');

    if (history && history.length > 0) {
      let html = '<div class="browser-list">';
      history.forEach(item => {
        html += `
          <div class="browser-item">
            <div class="browser-title">${escapeHtml(item.title || 'No Title')}</div>
            <div class="browser-url">${escapeHtml(item.url)}</div>
            <div class="browser-time">${formatDateTime(item.visit_time)}</div>
          </div>
        `;
      });
      html += '</div>';
      content.innerHTML = html;
    } else {
      content.innerHTML = '<p>ブラウザ履歴がありません</p>';
    }
  } catch (error) {
    console.error('Failed to load browser history:', error);
    showError('ブラウザ履歴の読み込みに失敗しました');
  }
}

/**
 * ニュースを読み込み
 */
async function loadNews() {
  try {
    const news = await window.api.getNews(50);
    const content = document.getElementById('newsContent');

    if (news && news.length > 0) {
      let html = '<div class="news-list">';
      news.forEach(item => {
        html += `
          <div class="news-item">
            <div class="news-title">${escapeHtml(item.title)}</div>
            <div class="news-meta">
              <span>${item.source || 'Unknown'}</span>
              <span>${formatDateTime(item.published_at || item.collected_at)}</span>
            </div>
          </div>
        `;
      });
      html += '</div>';
      content.innerHTML = html;
    } else {
      content.innerHTML = '<p>ニュースがありません</p>';
    }
  } catch (error) {
    console.error('Failed to load news:', error);
    showError('ニュースの読み込みに失敗しました');
  }
}

/**
 * レポートを読み込み
 */
async function loadReports() {
  try {
    const reports = await window.api.getReports(50);
    const content = document.getElementById('reportsContent');

    if (reports && reports.length > 0) {
      let html = '<div class="reports-list">';
      reports.forEach(item => {
        html += `
          <div class="report-item">
            <div class="report-title">${escapeHtml(item.title || 'Untitled Report')}</div>
            <div class="report-meta">
              <span>カテゴリ: ${item.category || 'general'}</span>
              <span>${formatDateTime(item.created_at)}</span>
            </div>
          </div>
        `;
      });
      html += '</div>';
      content.innerHTML = html;
    } else {
      content.innerHTML = '<p>レポートがありません</p>';
    }
  } catch (error) {
    console.error('Failed to load reports:', error);
    showError('レポートの読み込みに失敗しました');
  }
}

/**
 * タイムラインをレンダリング
 */
function renderTimeline(activities) {
  const container = document.getElementById('recentActivity');
  if (!container || !activities || activities.length === 0) return;

  const parentCard = container.closest('.card');
  if (parentCard) parentCard.style.display = 'block';

  let html = '';
  activities.forEach(activity => {
    html += `
      <div class="timeline-item">
        <div class="timeline-time">${formatDateTime(activity.timestamp)}</div>
        <div class="timeline-content">${escapeHtml(activity.description)}</div>
      </div>
    `;
  });

  container.innerHTML = html;
}

/**
 * ニュースをレンダリング
 */
function renderNews(newsList) {
  const container = document.getElementById('recentNews');
  if (!container || !newsList || newsList.length === 0) return;

  const parentCard = container.closest('.card');
  if (parentCard) parentCard.style.display = 'block';

  let html = '';
  newsList.forEach(news => {
    html += `
      <div class="news-item">
        <div class="news-title">${escapeHtml(news.title)}</div>
        <div class="news-meta">
          <span>${news.source || 'Unknown'}</span>
          <span>${formatDateTime(news.published_at || news.collected_at)}</span>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

/**
 * ボタン設定
 */
function setupButtons() {
  // 更新ボタン
  document.getElementById('refreshBtn')?.addEventListener('click', async () => {
    await refreshData();
  });

  // 最小化ボタン
  document.getElementById('minimizeBtn')?.addEventListener('click', async () => {
    await window.electronAPI.minimizeToTray();
  });

  // テーマ切り替えボタン
  document.getElementById('themeToggle')?.addEventListener('click', () => {
    toggleTheme();
  });
}

/**
 * テーマ設定
 */
async function setupTheme() {
  try {
    const settings = await window.electronAPI.getSettings();
    applyTheme(settings.theme);
  } catch (error) {
    console.error('Failed to setup theme:', error);
  }
}

/**
 * テーマを適用
 */
function applyTheme(theme) {
  if (theme === 'system') {
    // システムのダークモード設定を取得
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
  } else {
    document.documentElement.setAttribute('data-theme', theme);
  }

  // アイコンを更新
  const icon = document.querySelector('#themeToggle .icon');
  if (icon) {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    icon.textContent = currentTheme === 'dark' ? '☀️' : '🌙';
  }
}

/**
 * テーマを切り替え
 */
function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme');
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', newTheme);

  // アイコンを更新
  const icon = document.querySelector('#themeToggle .icon');
  if (icon) {
    icon.textContent = newTheme === 'dark' ? '☀️' : '🌙';
  }
}

/**
 * Electronイベントリスナー設定
 */
function setupElectronListeners() {
  // 自動更新
  window.electronAPI.onAutoRefresh(async () => {
    console.log('Auto refresh triggered');
    await refreshData();
  });

  // 強制更新
  window.electronAPI.onForceRefresh(async () => {
    console.log('Force refresh triggered');
    await refreshData();
  });

  // ページ遷移
  window.electronAPI.onNavigateTo((page) => {
    navigateTo(page);
  });

  // テーマ変更
  window.electronAPI.onThemeChanged((theme) => {
    applyTheme(theme);
  });
}

/**
 * データを更新
 */
async function refreshData() {
  await loadPageData(currentPage);
  updateLastUpdated();
}

/**
 * 最終更新時刻を更新
 */
function updateLastUpdated() {
  lastUpdateTime = new Date();
  const element = document.getElementById('lastUpdated');
  if (element) {
    element.textContent = `最終更新: ${formatTime(lastUpdateTime)}`;
  }
}

/**
 * エラーメッセージを表示
 */
function showError(message) {
  window.electronAPI.showNotification('エラー', message);
}

// ユーティリティ関数

/**
 * 時間をフォーマット
 */
function formatDuration(seconds) {
  if (!seconds || seconds < 0) return '0分';

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (hours > 0) {
    return `${hours}時間${minutes}分`;
  }
  return `${minutes}分`;
}

/**
 * 日時をフォーマット
 */
function formatDateTime(dateString) {
  if (!dateString) return '--';

  const date = new Date(dateString);
  const now = new Date();
  const diff = now - date;

  // 1分以内
  if (diff < 60000) {
    return 'たった今';
  }
  // 1時間以内
  if (diff < 3600000) {
    const minutes = Math.floor(diff / 60000);
    return `${minutes}分前`;
  }
  // 24時間以内
  if (diff < 86400000) {
    const hours = Math.floor(diff / 3600000);
    return `${hours}時間前`;
  }

  // それ以外
  return date.toLocaleString('ja-JP', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

/**
 * 時刻をフォーマット
 */
function formatTime(date) {
  return date.toLocaleTimeString('ja-JP', {
    hour: '2-digit',
    minute: '2-digit'
  });
}

/**
 * HTMLエスケープ
 */
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
