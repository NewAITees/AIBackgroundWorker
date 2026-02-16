"""Obsidianリンクセクション生成ユーティリティ."""

from pathlib import Path


def build_obsidian_links_section(output_dir: Path, report_date: str) -> str:
    """output_dir 内の article_{report_date}_*.md を検索し、Obsidian形式の関連記事セクションを返す.

    Args:
        output_dir: レポート出力ディレクトリ
        report_date: レポート対象日（YYYY-MM-DD）

    Returns:
        該当ファイルがあれば「## 関連記事」セクション文字列、なければ空文字
    """
    pattern = f"article_{report_date}_*.md"
    article_files = sorted(output_dir.glob(pattern))

    if not article_files:
        return ""

    lines = ["\n\n## 関連記事\n"]
    for f in article_files:
        stem = f.stem  # 拡張子なしのファイル名
        lines.append(f"- [[{stem}]]")

    return "\n".join(lines) + "\n"
