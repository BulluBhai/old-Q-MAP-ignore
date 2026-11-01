"""The planned Q-MAP modules, which application each belongs to, and their GENUINE readiness.

Only working functionality may be marked READY. Database Manager prepares data; Analytical Workbench analyses
prepared data. A planned module stays COMING SOON until its rules, parameters, outputs and validation criteria are
approved and implemented.
"""

from __future__ import annotations

from dataclasses import dataclass

READY = "ready"
COMING_SOON = "coming_soon"

DATABASE_MANAGER = "database_manager"
ANALYTICAL_WORKBENCH = "analytical_workbench"


@dataclass(frozen=True)
class ModuleInfo:
    key: str
    name: str
    description: str
    status: str
    note: str  # for READY: what works and what does not yet; for COMING_SOON: where it sits on the roadmap
    group: str  # heading on the Home screen
    app: str = ANALYTICAL_WORKBENCH
    screen: str = ""  # the screen its Open button shows (READY modules only)

    @property
    def is_ready(self) -> bool:
        return self.status == READY


_W, _R = "Application window", "Research module"

MODULES: tuple[ModuleInfo, ...] = (
    # ---- Database Manager --------------------------------------------------------------------------------------
    ModuleInfo("data_management", "Data Management",
               "Choose market-data files, preview them, check them and load them into Q-MAP.",
               READY,
               "Working now: preview, check without changes, load, results and report locations. "
               "Not built yet: restoring a damaged raw file from the screen (use the restore-raw command).",
               "Prepare data", DATABASE_MANAGER, "data"),
    ModuleInfo("datasets", "Datasets and Storage",
               "See every prepared dataset, its validation, location and lineage; mark it Permanent or Temporary; "
               "delete Temporary data; derive weekly, monthly, quarterly and yearly data from daily data.",
               READY,
               "Working now: dataset list and details, Permanent/Temporary moves, deleting Temporary datasets, "
               "derived timeframes from daily data. Not built yet: trading calendar, corporate actions.",
               "Manage data", DATABASE_MANAGER, "datasets"),
    # ---- Analytical Workbench: working tools --------------------------------------------------------------------
    ModuleInfo("dataset_summary", "Dataset Summary",
               "Coverage and descriptive statistics of prepared datasets, with a full run record. A utility for "
               "checking data before research - not a research methodology.",
               READY,
               "Working now: readiness checks, Run ID, CSV report and run metadata in Q-MAP_OUTPUT/Research_Reports.",
               "Available now", ANALYTICAL_WORKBENCH, "analysis"),
    # ---- Analytical Workbench: planned application windows ------------------------------------------------------
    ModuleInfo("dashboard", "Dashboard", "Daily starting point: market condition, sectors, saved screens.",
               COMING_SOON, "Needs Market Intelligence first (roadmap Stage 3).", _W),
    ModuleInfo("market_overview", "Market Overview", "Index trend, breadth, volatility and market regime.",
               COMING_SOON, "Roadmap Stage 3 (Market Intelligence).", _W),
    ModuleInfo("sector_explorer", "Sector Explorer", "Sector strength, rotation and constituents.",
               COMING_SOON, "Roadmap Stage 3 (Market Intelligence).", _W),
    ModuleInfo("stock_explorer", "Stock Explorer", "A detailed profile of one instrument.",
               COMING_SOON, "Roadmap Stage 3 (Market Intelligence).", _W),
    ModuleInfo("opportunity_scanner", "Opportunity Scanner",
               "Combine market, sector, stock and price-behaviour conditions to find candidates.",
               COMING_SOON, "Roadmap Stage 6.", _W),
    ModuleInfo("price_behaviour_lab", "Price Behaviour Lab", "Test how price behaves around moving averages and other events.",
               COMING_SOON, "Roadmap Stage 4 (QLOPB migration).", _W),
    ModuleInfo("strategy_lab", "Strategy Backtesting Lab", "Test complete trading rules on history.",
               COMING_SOON, "Roadmap Stage 7.", _W),
    ModuleInfo("portfolio_risk", "Portfolio and Risk", "Position sizing, exposure and drawdown.",
               COMING_SOON, "Roadmap Stage 8.", _W),
    ModuleInfo("research_library", "Research Library", "Saved findings, evidence and experiment history.",
               COMING_SOON, "The database tables and run records exist, but there is no screen or workflow yet.", _W),
    # ---- Analytical Workbench: planned research modules ---------------------------------------------------------
    ModuleInfo("market_intelligence", "Market Intelligence (MIQP)", "Market regime, breadth, sector and stock intelligence.",
               COMING_SOON, "Roadmap Stage 3. MIQP is specified in documents outside this repository; no MIQP code "
               "exists yet.", _R),
    ModuleInfo("ma_research", "MA Research (QLOPB)", "Moving-average interactions and affinity.",
               COMING_SOON, "Roadmap Stage 4. The QLOPB source code is not in this repository yet, so nothing has been "
               "migrated.", _R),
    ModuleInfo("cpr_pivot", "CPR and Pivot Research", "Central Pivot Range and pivot-level behaviour.",
               COMING_SOON, "Roadmap Stage 4.", _R),
    ModuleInfo("stage_analysis", "Stage Analysis (Weinstein)", "Classify instruments into price stages.",
               COMING_SOON, "Roadmap Stage 5. Needs explicit, approved rules, parameters and validation criteria "
               "first.", _R),
    ModuleInfo("ichimoku", "Ichimoku Research", "Cloud and component behaviour.",
               COMING_SOON, "Roadmap Stage 5.", _R),
    ModuleInfo("candlesticks", "Candlestick Research", "Pattern behaviour and combinations.",
               COMING_SOON, "Roadmap Stage 5.", _R),
    ModuleInfo("volume_research", "Volume Research", "Volume and price relationships.",
               COMING_SOON, "Roadmap Stage 5.", _R),
    ModuleInfo("proprietary", "Proprietary Research", "Your own observations turned into testable rules.",
               COMING_SOON, "Roadmap Stage 5.", _R),
)


def modules_for(app: str) -> list[ModuleInfo]:
    return [m for m in MODULES if m.app == app]


def ready_modules(app: str | None = None) -> list[ModuleInfo]:
    return [m for m in MODULES if m.is_ready and (app is None or m.app == app)]
