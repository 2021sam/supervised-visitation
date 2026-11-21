"""Live, six-stage county acquisition progress reporting."""

from dataclasses import dataclass, field


STAGES = (
    "Loading county configuration and previous results",
    "Connecting to county court website",
    "Discovering navigation menus and controls",
    "Collecting and deduplicating links",
    "Ranking links using AI",
    "Exploring relevant website branches",
    "Identifying candidate directories and documents",
    "Ranking and selecting candidate documents",
    "Downloading selected documents",
    "Classifying and extracting document contents",
    "Validating directories and provider records",
    "Saving results and updating county status",
)


@dataclass
class CountyProgress:
    state: str
    county: str
    index: int
    total: int
    counters: dict = field(default_factory=dict)

    def update(self, step, *, status="running", **counters):
        """Report a stage transition or updated processing counters."""
        if not 1 <= step <= len(STAGES):
            raise ValueError(f"Invalid progress step: {step}")

        if status not in {"running", "completed", "skipped", "failed"}:
            raise ValueError(f"Invalid progress status: {status}")

        self.counters.update(counters)

        prefix = (
            f"[{self.state} {self.index}/{self.total}] "
            f"{self.county}"
        )

        print(
            f"{prefix} | Step {step} of {len(STAGES)}: "
            f"{STAGES[step - 1]} [{status}]",
            flush=True,
        )

        if self.counters:
            metrics = " | ".join(
                f"{key.replace('_', ' ').title()}: {value}"
                for key, value in self.counters.items()
            )
            print(f"  {metrics}", flush=True)
