"""Select registered extraction strategies and report outcomes."""

from dataclasses import dataclass, field

from .provenance import enrich_records
from .defaults import build_default_registry
from .registry import StrategyRegistry
from .strategies.pdf_layout import PDFLayoutConfig


@dataclass
class ExtractionResult:
    status: str
    strategy: str | None = None
    records: list[dict] = field(default_factory=list)
    reason: str = ""




def extract_document(
    content: bytes,
    *,
    content_type: str,
    source_url: str | None = None,
    pdf_config: PDFLayoutConfig | None = None,
    start_page: int = 0,
    item_selector: str | None = None,
    field_selectors: dict[str, str] | None = None,
    registry: StrategyRegistry | None = None,
    config: dict | None = None,
) -> ExtractionResult:
    """Execute the first configured, compatible strategy.

    Strategies are tried in registration order.
    Records are extracted but not independently verified.
    """
    registry = (
        registry
        if registry is not None
        else build_default_registry()
    )

    compatible = registry.compatible(content_type)

    if not compatible:
        normalized = content_type.split(";")[0].strip().lower()
        return ExtractionResult(
            status="unsupported_format",
            reason=f"Unsupported content type: {normalized}",
        )

    configuration = {
        "pdf_config": pdf_config,
        "start_page": start_page,
        "item_selector": item_selector,
        "field_selectors": field_selectors,
        "source_url": source_url,
    }

    if config is not None:
        configuration.update(config)

    # The explicit source URL is authoritative for provenance.
    configuration["source_url"] = source_url

    missing_configuration = False
    attempted = []

    for strategy in compatible:
        if strategy.missing_config(configuration):
            missing_configuration = True
            continue

        if strategy.prepare_kwargs is not None:
            kwargs = strategy.prepare_kwargs(configuration)
        else:
            kwargs = {"source_url": source_url}

        attempted.append(strategy.name)

        try:
            records = strategy.extract(content, **kwargs)
        except (ValueError, RuntimeError) as exc:
            return ExtractionResult(
                status="extraction_failed",
                strategy=strategy.name,
                reason=str(exc),
            )

        if records:
            return ExtractionResult(
                status="extracted_unverified",
                strategy=strategy.name,
                records=enrich_records(
                    records,
                    strategy=strategy.name,
                    source_url=source_url,
                ),
            )

    # Automatic strategies may run without producing records.
    # Preserve the legacy configuration and fallback contract.
    automatic_strategies = {
        "pdf_service_table",
        "pdf_provider_profiles",
        "pdf_label_value",
        "pdf_provider_tables",
    }
    configured_attempts = [
        name for name in attempted
        if name not in automatic_strategies
    ]

    if configured_attempts:
        return ExtractionResult(
            status="needs_fallback",
            strategy=configured_attempts[-1],
            reason="No records detected by configured strategies",
        )

    if missing_configuration:
        return ExtractionResult(
            status="needs_configuration",
            reason="Compatible strategies require configuration",
        )

    if attempted:
        return ExtractionResult(
            status="needs_fallback",
            strategy=attempted[-1],
            reason="No records detected by automatic strategies",
        )

    return ExtractionResult(
        status="needs_fallback",
        reason="No applicable extraction strategy",
    )
