"""The planned Q-MAP modules and their GENUINE readiness. Only working functionality may be marked READY."""

from __future__ import annotations

from dataclasses import dataclass

READY = "ready"
COMING_SOON = "coming_soon"


@dataclass(frozen=True)
class ModuleInfo:
    key: str
    name: str
    description: str
    status: str
    note: str  # for READY: what works and what does not yet; for COMING_SOON: where it sits on the roadmap
    group: str  # "Application window" or "Research module" (Blueprint sections 5 and 6)

    @property
    def is_ready(self) -> bool:
        return self.status == READY


MODULES: tuple[ModuleInfo, ...] = (
    ModuleInfo("data_management", "Data Management",
               "Choose market-data files, preview them, check them and load them into Q-MAP.",
               READY,
               "Working now: preview, check without changes, ingest, results and report locations. "
               "Not built yet: data coverage view, restoring a damaged raw file from the screen.",
               "Application window"),
    ModuleInfo("dashboard", "Dashboard", "Daily starting point: market condition, sectors, saved screens.",
               COMING_SOON, "Needs Market Intelligence first (roadmap Stage 3).", "Application window"),
    ModuleInfo("market_overview", "Market Overview", "Index trend, breadth, volatility and market regime.",
               COMING_SOON, "Roadmap Stage 3 (Market Intelligence).", "Application window"),
    ModuleInfo("sector_explorer", "Sector Explorer", "Sector strength, rotation and constituents.",
               COMING_SOON, "Roadmap Stage 3 (Market Intelligence).", "Application window"),
    ModuleInfo("stock_explorer", "Stock Explorer", "A detailed profile of one instrument.",
               COMING_SOON, "Roadmap Stage 3 (Market Intelligence).", "Application window"),
    ModuleInfo("opportunity_scanner", "Opportunity Scanner",
               "Combine market, sector, stock and price-behaviour conditions to find candidates.",
               COMING_SOON, "Roadmap Stage 6.", "Application window"),
    ModuleInfo("price_behaviour_lab", "Price Behaviour Lab", "Test how price behaves around moving averages and other events.",
               COMING_SOON, "Roadmap Stage 4 (QLOPB migration).", "Application window"),
    ModuleInfo("strategy_lab", "Strategy Backtesting Lab", "Test complete trading rules on history.",
               COMING_SOON, "Roadmap Stage 7.", "Application window"),
    ModuleInfo("portfolio_risk", "Portfolio and Risk", "Position sizing, exposure and drawdown.",
               COMING_SOON, "Roadmap Stage 8.", "Application window"),
    ModuleInfo("research_library", "Research Library", "Saved findings, evidence and experiment history.",
               COMING_SOON, "The database tables exist, but there is no screen or workflow yet.", "Application window"),
    ModuleInfo("market_intelligence", "Market Intelligence (MIQP)", "Market regime, breadth, sector and stock intelligence.",
               COMING_SOON, "Roadmap Stage 3. MIQP is specified but not implemented.", "Research module"),
    ModuleInfo("ma_research", "MA Research (QLOPB)", "Moving-average interactions and affinity.",
               COMING_SOON, "Roadmap Stage 4. QLOPB code has not been migrated yet.", "Research module"),
    ModuleInfo("cpr_pivot", "CPR and Pivot Research", "Central Pivot Range and pivot-level behaviour.",
               COMING_SOON, "Roadmap Stage 4.", "Research module"),
    ModuleInfo("ichimoku", "Ichimoku Research", "Cloud and component behaviour.",
               COMING_SOON, "Roadmap Stage 5.", "Research module"),
    ModuleInfo("candlesticks", "Candlestick Research", "Pattern behaviour and combinations.",
               COMING_SOON, "Roadmap Stage 5.", "Research module"),
    ModuleInfo("volume_research", "Volume Research", "Volume and price relationships.",
               COMING_SOON, "Roadmap Stage 5.", "Research module"),
    ModuleInfo("proprietary", "Proprietary Research", "Your own observations turned into testable rules.",
               COMING_SOON, "Roadmap Stage 5.", "Research module"),
)


def ready_modules() -> list[ModuleInfo]:
    return [m for m in MODULES if m.is_ready]
