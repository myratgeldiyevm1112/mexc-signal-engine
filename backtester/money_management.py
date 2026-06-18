"""
backtester/money_management.py

Simulates money management on top of backtest signals.

Rules:
  - Deposit starts at INITIAL_DEPOSIT
  - Each trade risks RISK_PERCENT of CURRENT deposit (not initial)
  - Leverage: 10x  → real position = stake * 10
  - TP: entry_price ± swing_move * FIB_LEVEL  (61.8% extension)
      swing_move = abs(change_15m / 100 * entry_price)
      LONG  TP = entry_price + swing_move * 0.618
      SHORT TP = entry_price - swing_move * 0.618
  - SL: lose the entire stake (-RISK_PERCENT of deposit)
  - Commission: COMMISSION_PCT of position size, charged on entry AND exit
  - Outcomes are checked in order: 1h → 4h → 24h
      If price reached TP within the window → WIN
      If price never reached TP in any window → LOSE (SL hit)
"""
from __future__ import annotations

import pandas as pd
from dataclasses import dataclass, field
from pathlib import Path

# ── настройки ──────────────────────────────────────────────
INITIAL_DEPOSIT   = 100.0   # $
RISK_PERCENT      = 0.01    # 1% of current deposit per trade
LEVERAGE          = 10      # 10x
FIB_LEVEL         = 0.618   # 61.8% fibonacci extension
COMMISSION_PCT    = 0.001   # 0.1% per side (taker fee MEXC)
# ───────────────────────────────────────────────────────────


@dataclass
class TradeResult:
    symbol:       str
    direction:    str
    entry_time:   pd.Timestamp
    entry_price:  float
    change_15m:   float
    tp_price:     float
    sl_pct:       float        # % move needed to hit SL
    stake:        float        # $ risked
    position:     float        # stake * leverage
    commission:   float        # total commission (entry + exit)
    outcome:      str          # "WIN" | "LOSE"
    pnl_usd:      float        # net P&L in $
    deposit_after: float       # deposit after this trade
    win_window:   str | None   # "1h" / "4h" / "24h" / None


@dataclass
class MMReport:
    trades:          list[TradeResult] = field(default_factory=list)
    initial_deposit: float = INITIAL_DEPOSIT

    # ── computed properties ──────────────────────────────
    @property
    def final_deposit(self) -> float:
        return self.trades[-1].deposit_after if self.trades else self.initial_deposit

    @property
    def total_pnl(self) -> float:
        return self.final_deposit - self.initial_deposit

    @property
    def roi(self) -> float:
        return self.total_pnl / self.initial_deposit * 100

    @property
    def win_count(self) -> int:
        return sum(1 for t in self.trades if t.outcome == "WIN")

    @property
    def lose_count(self) -> int:
        return sum(1 for t in self.trades if t.outcome == "LOSE")

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        return self.win_count / len(self.trades) * 100

    @property
    def max_drawdown(self) -> float:
        """Max drawdown from peak in $."""
        peak = self.initial_deposit
        max_dd = 0.0
        deposit = self.initial_deposit
        for t in self.trades:
            deposit = t.deposit_after
            peak = max(peak, deposit)
            dd = peak - deposit
            max_dd = max(max_dd, dd)
        return max_dd

    @property
    def max_drawdown_pct(self) -> float:
        peak = self.initial_deposit
        max_dd_pct = 0.0
        deposit = self.initial_deposit
        for t in self.trades:
            deposit = t.deposit_after
            peak = max(peak, deposit)
            if peak > 0:
                dd_pct = (peak - deposit) / peak * 100
                max_dd_pct = max(max_dd_pct, dd_pct)
        return max_dd_pct

    @property
    def max_losing_streak(self) -> int:
        streak = max_streak = 0
        for t in self.trades:
            if t.outcome == "LOSE":
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        return max_streak

    @property
    def equity_curve(self) -> list[float]:
        curve = [self.initial_deposit]
        for t in self.trades:
            curve.append(t.deposit_after)
        return curve


def simulate(df: pd.DataFrame) -> MMReport:
    """
    Run money management simulation on signals DataFrame.

    df must have columns:
      symbol, direction, entry_time, entry_price, change_15m,
      outcome_1h, outcome_4h, outcome_24h
    """
    # Sort signals by entry_time
    df = df.sort_values("entry_time").reset_index(drop=True)

    deposit = INITIAL_DEPOSIT
    report = MMReport(initial_deposit=INITIAL_DEPOSIT)

    for _, row in df.iterrows():
        if deposit <= 0:
            break

        entry_price = float(row["entry_price"])
        change_15m  = float(row["change_pct"])   # % (positive for LONG, negative for SHORT in raw data)
        direction   = row["direction"]

        # ── Stake & position ────────────────────────────
        stake    = deposit * RISK_PERCENT          # $ at risk
        position = stake * LEVERAGE                # real position size

        # ── Commission ──────────────────────────────────
        commission = position * COMMISSION_PCT * 2  # entry + exit

        # ── TP calculation (Fibonacci 61.8% extension) ──
        # swing_move = price move that triggered the signal
        swing_move = abs(change_15m / 100 * entry_price)
        fib_move   = swing_move * FIB_LEVEL

        if direction == "LONG":
            tp_price = entry_price + fib_move
            tp_pct   = fib_move / entry_price * 100   # % gain needed to hit TP
        else:  # SHORT
            tp_price = entry_price - fib_move
            tp_pct   = fib_move / entry_price * 100   # % drop needed to hit TP

        # ── SL: lose entire stake ───────────────────────
        # How much % price must move against us to lose the stake?
        # loss = position * sl_pct → sl_pct = stake / position = 1/LEVERAGE
        sl_pct = 1.0 / LEVERAGE * 100  # = 10% price move (with 10x leverage)

        # ── Determine outcome ───────────────────────────
        # outcome_Xh = % price change after Xh (positive = good for direction)
        outcome = "LOSE"
        win_window = None

        for window in ["outcome_1h", "outcome_4h", "outcome_24h"]:
            val = row.get(window)
            if pd.isna(val) or val is None:
                continue
            val = float(val)
            # val is already direction-adjusted in engine.py (positive = profit)
            if val >= tp_pct:
                outcome = "WIN"
                win_window = window.replace("outcome_", "")
                break
            # Check if SL was hit (price moved -sl_pct against us)
            # We approximate: if outcome is very negative, SL was hit
            # (conservative: if val <= -sl_pct we assume SL hit in this window)

        # ── P&L calculation ─────────────────────────────
        if outcome == "WIN":
            # profit = position * tp_pct%
            gross_pnl = position * (tp_pct / 100)
            pnl = gross_pnl - commission
        else:
            # lose entire stake (commission already paid)
            pnl = -stake - commission

        deposit = max(0.0, deposit + pnl)

        report.trades.append(TradeResult(
            symbol       = row["symbol"],
            direction    = direction,
            entry_time   = row["entry_time"],
            entry_price  = entry_price,
            change_15m   = change_15m,
            tp_price     = round(tp_price, 8),
            sl_pct       = round(sl_pct, 2),
            stake        = round(stake, 4),
            position     = round(position, 4),
            commission   = round(commission, 4),
            outcome      = outcome,
            pnl_usd      = round(pnl, 4),
            deposit_after= round(deposit, 4),
            win_window   = win_window,
        ))

    return report


def print_report(report: MMReport) -> None:
    trades_df = pd.DataFrame([vars(t) for t in report.trades])

    print("\n" + "=" * 60)
    print("      MONEY MANAGEMENT REPORT — MEXC Signal Engine")
    print("=" * 60)

    print(f"\n💰 Initial deposit : ${report.initial_deposit:.2f}")
    print(f"💰 Final deposit   : ${report.final_deposit:.2f}")
    print(f"📈 Total P&L       : ${report.total_pnl:+.2f}")
    print(f"📊 ROI             : {report.roi:+.2f}%")

    print(f"\n🎯 Total trades    : {len(report.trades)}")
    print(f"   WIN             : {report.win_count}")
    print(f"   LOSE            : {report.lose_count}")
    print(f"   Win Rate        : {report.win_rate:.1f}%")

    print(f"\n📉 Max Drawdown    : ${report.max_drawdown:.2f} ({report.max_drawdown_pct:.1f}%)")
    print(f"🔴 Max Lose Streak : {report.max_losing_streak}")

    # Win windows breakdown
    if not trades_df.empty:
        wins = trades_df[trades_df["outcome"] == "WIN"]
        if not wins.empty:
            print("\n⏱  Win by window:")
            for w in ["1h", "4h", "24h"]:
                cnt = (wins["win_window"] == w).sum()
                print(f"   {w:>4} : {cnt} wins")

    # By direction
    print("\n" + "-" * 60)
    print("By direction:")
    for direction in ["LONG", "SHORT"]:
        sub = trades_df[trades_df["direction"] == direction]
        if sub.empty:
            continue
        wins_sub = (sub["outcome"] == "WIN").sum()
        wr = wins_sub / len(sub) * 100
        avg_pnl = sub["pnl_usd"].mean()
        total_pnl = sub["pnl_usd"].sum()
        print(f"\n  {direction}: {len(sub)} trades | WR: {wr:.1f}% | Avg P&L: ${avg_pnl:+.3f} | Total: ${total_pnl:+.2f}")

    # Top symbols by P&L
    print("\n" + "-" * 60)
    print("Top 10 symbols by total P&L:")
    sym_pnl = trades_df.groupby("symbol")["pnl_usd"].sum().sort_values(ascending=False)
    for sym, pnl in sym_pnl.head(10).items():
        cnt = len(trades_df[trades_df["symbol"] == sym])
        print(f"  {sym:<22} {cnt:>3} trades   P&L: ${pnl:+.3f}")

    print("\n" + "-" * 60)
    print("Bottom 10 symbols by total P&L:")
    for sym, pnl in sym_pnl.tail(10).items():
        cnt = len(trades_df[trades_df["symbol"] == sym])
        print(f"  {sym:<22} {cnt:>3} trades   P&L: ${pnl:+.3f}")

    print("\n" + "=" * 60)

    # Save
    out_path = Path("backtester/mm_results.csv")
    trades_df.to_csv(out_path, index=False)
    print(f"\n💾 Full MM results saved to {out_path}")
    print("=" * 60 + "\n")