/**
 * APIクライアント
 * viewer_service のAPIと通信するモジュール
 */

class APIClient {
  constructor() {
    this.baseURL = 'http://localhost:8000';
    this.loadSettings();
  }

  /**
   * 設定を読み込み
   */
  async loadSettings() {
    try {
      const settings = await window.electronAPI.getSettings();
      this.baseURL = settings.apiEndpoint;
    } catch (error) {
      console.error('Failed to load settings:', error);
    }
  }

  /**
   * APIリクエストを送信
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;

    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error);
      throw error;
    }
  }

  /**
   * ダッシュボードデータを取得
   */
  async getDashboard() {
    return await this.request('/api/dashboard');
  }

  /**
   * ライフログサマリーを取得
   */
  async getLifelogSummary(date = null) {
    const params = date ? `?date=${date}` : '';
    return await this.request(`/api/lifelog/summary${params}`);
  }

  /**
   * ライフログの時間帯別アクティビティを取得
   */
  async getLifelogHourly(date = null) {
    const params = date ? `?date=${date}` : '';
    return await this.request(`/api/lifelog/hourly${params}`);
  }

  /**
   * ライフログのタイムラインを取得
   */
  async getLifelogTimeline(hours = 24) {
    return await this.request(`/api/lifelog/timeline?hours=${hours}`);
  }

  /**
   * ブラウザ履歴を取得
   */
  async getBrowserHistory(limit = 50, offset = 0) {
    return await this.request(`/api/browser/recent?limit=${limit}&offset=${offset}`);
  }

  /**
   * ブラウザ履歴の統計を取得
   */
  async getBrowserStats(date = null) {
    const params = date ? `?date=${date}` : '';
    return await this.request(`/api/browser/stats${params}`);
  }

  /**
   * ニュース一覧を取得
   */
  async getNews(limit = 50, offset = 0) {
    return await this.request(`/api/info/news?limit=${limit}&offset=${offset}`);
  }

  /**
   * RSS一覧を取得
   */
  async getRSS(limit = 50, offset = 0) {
    return await this.request(`/api/info/rss?limit=${limit}&offset=${offset}`);
  }

  /**
   * 検索結果を取得
   */
  async getSearchResults(limit = 50, offset = 0) {
    return await this.request(`/api/info/search?limit=${limit}&offset=${offset}`);
  }

  /**
   * レポート一覧を取得
   */
  async getReports(limit = 50, offset = 0) {
    return await this.request(`/api/info/reports?limit=${limit}&offset=${offset}`);
  }

  /**
   * レポートの詳細を取得
   */
  async getReportDetail(reportId) {
    return await this.request(`/api/info/reports/${reportId}`);
  }

  /**
   * ヘルスメトリクスを取得
   */
  async getHealthMetrics(hours = 24) {
    return await this.request(`/api/lifelog/health?hours=${hours}`);
  }

  /**
   * API接続をテスト
   */
  async testConnection() {
    try {
      const response = await fetch(`${this.baseURL}/api/dashboard`);
      return response.ok;
    } catch (error) {
      return false;
    }
  }
}

// グローバルに公開
window.api = new APIClient();
