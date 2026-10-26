from app.infrastructure.services.cron_expression import CronExpressionValidator


def test_cron_expression_validator_accepts_six_and_seven_field_expressions() -> None:
    assert CronExpressionValidator.validate_cron_expression('0 0 8 * * ?')
    assert CronExpressionValidator.validate_cron_expression('0 0 8 * * ? 2026')


def test_cron_expression_validator_rejects_invalid_field_count_and_ranges() -> None:
    assert not CronExpressionValidator.validate_cron_expression('0 0 8 * *')
    assert not CronExpressionValidator.validate_cron_expression('0 0 25 * * ?')
