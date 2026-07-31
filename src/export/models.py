"""Typed export rows, categories, and immutable SQLite snapshots."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum


class ExportCategory(StrEnum):
    """Supported CSV and workbook result partitions."""

    ALL_RESULTS = "all_results"
    BUSINESS_TARGETS = "business_targets"
    MOBILE_ONLY = "mobile_only"
    NO_PHONE = "no_phone"
    REVIEW_REQUIRED = "review_required"
    EXCLUDED = "excluded"
    ERRORS = "errors"


@dataclass(frozen=True, slots=True)
class ExportRow:
    """One flattened, display-ready row read exclusively from SQLite."""

    id: int
    company_name: str
    store_name: str
    display_name: str
    search_industry: str
    estimated_industry: str
    primary_phone: str
    mobile_phones: str
    fixed_phones: str
    all_phone_numbers: str
    phone_usages: str
    postal_code: str
    prefecture: str
    municipality: str
    address: str
    official_url: str
    source_url: str
    search_prefecture: str
    search_municipality: str
    search_word: str
    search_query: str
    search_provider: str
    search_rank: int | None
    official_score: int | None
    business_score: int | None
    is_official: bool
    is_business_target: bool
    review_required: bool
    exclusion_reasons: str
    positive_signals: str
    negative_signals: str
    http_status: int | None
    processing_status: str
    fetched_at: str
    last_checked_at: str
    error_message: str = ""
    duplicate_candidate: bool = False
    all_search_conditions: str = ""


@dataclass(frozen=True, slots=True)
class ExportSnapshot:
    """Consistent result and error rows captured in one SQLite read transaction."""

    rows: tuple[ExportRow, ...]
    errors: tuple[ExportRow, ...]
    sales_rows: tuple[ExportRow, ...] = ()

    def __post_init__(self) -> None:
        """Use all rows as sales rows for manually constructed snapshots."""
        if self.rows and not self.sales_rows:
            object.__setattr__(self, "sales_rows", self.rows)

    def rows_for(self, category: ExportCategory) -> tuple[ExportRow, ...]:
        """Return a deterministic partition without reading another data source."""
        filters = {
            ExportCategory.ALL_RESULTS: lambda row: True,
            ExportCategory.BUSINESS_TARGETS: lambda row: row.is_business_target,
            ExportCategory.MOBILE_ONLY: lambda row: bool(row.mobile_phones),
            ExportCategory.NO_PHONE: lambda row: not row.all_phone_numbers,
            ExportCategory.REVIEW_REQUIRED: lambda row: row.review_required,
            ExportCategory.EXCLUDED: lambda row: not row.is_business_target,
            ExportCategory.ERRORS: lambda row: bool(row.error_message),
        }
        if category is ExportCategory.ERRORS:
            source = self.errors
        elif category is ExportCategory.ALL_RESULTS:
            source = self.rows
        else:
            source = self.sales_rows
        return tuple(row for row in source if filters[category](row))

    def with_first_company_name(self, value: str) -> ExportSnapshot:
        """Return a test-friendly copy with one changed display value."""
        if not self.rows:
            return self
        first = replace(self.rows[0], company_name=value)
        rows = (first, *self.rows[1:])
        errors = tuple(first if row.id == first.id else row for row in self.errors)
        sales = tuple(first if row.id == first.id else row for row in self.sales_rows)
        return ExportSnapshot(rows, errors, sales)


HEADERS: tuple[tuple[str, str], ...] = (
    ("id", "ID"),
    ("company_name", "法人名"),
    ("store_name", "店舗名"),
    ("display_name", "表示名"),
    ("search_industry", "検索業種"),
    ("estimated_industry", "推定業種"),
    ("primary_phone", "電話番号"),
    ("mobile_phones", "携帯電話番号"),
    ("fixed_phones", "固定電話番号"),
    ("all_phone_numbers", "全電話番号"),
    ("phone_usages", "電話番号用途"),
    ("postal_code", "郵便番号"),
    ("prefecture", "都道府県"),
    ("municipality", "市区町村"),
    ("address", "住所"),
    ("official_url", "公式HP"),
    ("source_url", "情報取得ページ"),
    ("search_prefecture", "検索都道府県"),
    ("search_municipality", "検索市区町村"),
    ("search_word", "検索ワード"),
    ("search_query", "検索クエリ"),
    ("search_provider", "検索Provider"),
    ("search_rank", "検索順位"),
    ("official_score", "公式サイトスコア"),
    ("business_score", "営業対象スコア"),
    ("is_official", "公式サイト判定"),
    ("is_business_target", "営業対象判定"),
    ("review_required", "要確認"),
    ("exclusion_reasons", "除外理由"),
    ("positive_signals", "加点理由"),
    ("negative_signals", "減点理由"),
    ("http_status", "HTTPステータス"),
    ("processing_status", "処理状態"),
    ("error_message", "エラーメッセージ"),
    ("duplicate_candidate", "重複候補"),
    ("all_search_conditions", "全検索条件"),
    ("fetched_at", "取得日時"),
    ("last_checked_at", "最終確認日時"),
)
