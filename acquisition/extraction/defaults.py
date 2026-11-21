from .strategies.pdf_provider_tables import extract_pdf_provider_tables
"""Built-in extraction strategy registrations."""

from .registry import Strategy, StrategyRegistry
from .strategies.json_api import extract_json_records
from .strategies.pdf_layout import PDFLayoutConfig, extract_pdf_rows
from .strategies.pdf_columns import extract_pdf_columns
from .strategies.pdf_service_table import extract_pdf_service_table
from .strategies.pdf_provider_profiles import extract_pdf_provider_profiles
from .strategies.pdf_label_value import extract_pdf_label_value
from .strategies.pdf_text_table import PDFTextTableConfig, extract_pdf_text_table
from .strategies.html_table import extract_html_tables
from .strategies.html_repeated import extract_html_repeated


"""Built-in extraction strategy registrations."""

from .registry import Strategy, StrategyRegistry
from .docling_pdf import extract_docling_pdf
from .strategies.json_api import extract_json_records
from .strategies.html_table import extract_html_tables
from .strategies.html_repeated import extract_html_repeated


def build_default_registry() -> StrategyRegistry:
    """Register Docling-only PDF and existing non-PDF strategies."""
    registry = StrategyRegistry()

    registry.register(
        Strategy(
            name="docling_pdf",
            content_types=("application/pdf",),
            extract=extract_docling_pdf,
            prepare_kwargs=lambda config: {
                "source_url": config.get("source_url"),
            },
        )
    )

    registry.register(
        Strategy(
            name="html_table",
            content_types=("text/html", "application/xhtml+xml"),
            extract=extract_html_tables,
            prepare_kwargs=lambda config: {
                "source_url": config.get("source_url"),
            },
        )
    )

    registry.register(
        Strategy(
            name="html_repeated",
            content_types=("text/html", "application/xhtml+xml"),
            extract=extract_html_repeated,
            required_config=("item_selector", "field_selectors"),
            prepare_kwargs=lambda config: {
                "item_selector": config["item_selector"],
                "field_selectors": config["field_selectors"],
                "source_url": config.get("source_url"),
            },
        )
    )

    registry.register(
        Strategy(
            name="json_api",
            content_types=("application/json",),
            extract=extract_json_records,
            prepare_kwargs=lambda config: {
                "records_path": config.get("records_path", ""),
                "source_url": config.get("source_url"),
            },
        )
    )

    return registry
