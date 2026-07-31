"""Phase 8 Step 5 StatusService aggregation tests."""

from status.service import StatusService


def test_aggregates_status_without_printing(populated_database) -> None:
    status = StatusService(populated_database).get_status()

    assert status.search_condition_count == 3
    assert status.completed_condition_count == 1
    assert status.pending_condition_count == 1
    assert status.processing_condition_count == 1
    assert status.business_target_count == 2
    assert status.official_count == 3
    assert status.mobile_count == 1
    assert status.no_phone_count == 1
    assert status.review_required_count == 1
    assert status.excluded_count >= 2
    assert status.error_count == 1
    assert status.total_processed_count == 5
    assert status.retry_waiting_count == 1
    assert status.current_urls == ("https://running.example/",)
    assert status.next_retry_at == "2099-01-01 00:00:00"
