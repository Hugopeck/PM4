# PM4 Dry-Run Guide: Human-in-the-Loop Safety Validation

## 🎯 **Purpose**

This guide walks you through a comprehensive dry-run process to validate your PM4 market making bot **before risking real capital**. The goal is to manually verify:

- ✅ Calibration accuracy and market conditions
- ✅ Mathematical model integrity
- ✅ Quote generation logic
- ✅ Risk management sanity
- ✅ Real-world market alignment

**Why this matters**: Market making involves complex risk models. A 5-minute dry-run can prevent costly mistakes.

---

## 📋 **Prerequisites**

### Environment Setup
```bash
# Ensure you have these environment variables set
export PK="your_private_key_here"
export CLOB_API_KEY="your_api_key"          # Optional but recommended
export CLOB_SECRET="your_api_secret"        # Optional but recommended
export CLOB_PASS_PHRASE="your_passphrase"    # Optional but recommended
export FUNDER_ADDRESS="your_funder_address"  # Optional for gasless trading
```

### Available Tools
PM4 now includes automated tools to help with market analysis and configuration:

```bash
# 🧮 MARKET ANALYZER: Automatically evaluate market suitability for PM4 trading
# This tool analyzes volume, liquidity, trader activity, and market conditions
# to give you an objective recommendation before you invest time configuring
# Accepts both full URLs and simple market slugs for maximum flexibility
python -m pm4.market_analyzer "https://polymarket.com/market/ethereum-to-10k-before-2025"
# OR simply: python -m pm4.market_analyzer "ethereum-to-10k-before-2025"

# ⚙️ CONFIG HELPER (URL Mode): Extract market info from Polymarket URLs
# Automatically fetches market details and generates a complete config.json template
# Saves you from manually looking up condition IDs, asset IDs, and timestamps
python -m pm4.market_config_helper "https://polymarket.com/market/ethereum-to-10k-before-2025"

# 🎯 INTERACTIVE CONFIG HELPER: Guided step-by-step configuration
# Walks you through selecting a market and setting up your config interactively
# Perfect for first-time users who want hand-holding through the process
python -m pm4.market_config_helper --interactive
```

#### **How These Tools Work (Detailed Explanation)**

**1. Market Analyzer (`pm4.market_analyzer`)**

**What it does:**
- Connects to Polymarket's API to fetch real-time market data
- Analyzes 5 key factors: volume, active traders, recent activity, time-to-resolution, and price positioning
- Scores the market on a 0-7 scale based on objective criteria
- Provides a RECOMMENDED/CONDITIONAL/NOT_RECOMMENDED rating
- Shows detailed reasoning for the score

**Why it's valuable:**
- **Time-saving**: Instantly identifies unsuitable markets (low volume, stagnant, etc.)
- **Risk reduction**: Prevents you from wasting time on markets that won't work for PM4
- **Education**: Teaches you what makes a "good" market for market making
- **Objectivity**: Removes guesswork with data-driven analysis

**Example workflows:**
```
Input: "https://polymarket.com/market/will-ethereum-reach-100k"
Output: "RECOMMENDED - High volume ($250k), 150+ traders, active trading"

Input: "will-ethereum-reach-100k"  (slug only)
Output: "RECOMMENDED - High volume ($250k), 150+ traders, active trading"
```

**2. Config Helper URL Mode (`pm4.market_config_helper <url>`)**

**What it does:**
- Takes a Polymarket URL and extracts the market slug automatically
- Calls the Market Analyzer to validate the market
- Generates a complete `config.json` template with:
  - Market condition ID and asset IDs (auto-filled)
  - Proper timestamp conversion for start/end dates
  - Safe default parameters for testing
  - Market analysis summary included as comments

**Why it's valuable:**
- **Automation**: No more manual URL parsing or ID lookup
- **Safety**: Includes market validation before generating config
- **Completeness**: Creates production-ready config files
- **Integration**: Combines analysis + configuration in one step

**Example workflow:**
```
Input: "https://polymarket.com/market/will-btc-hit-100k-this-year"
Output: Complete config.json with all IDs filled in + market analysis
```

**3. Interactive Config Helper (`pm4.market_config_helper --interactive`)**

**What it does:**
- Starts an interactive command-line wizard
- Asks you to paste a Polymarket URL
- Validates the URL format and extracts market information
- Lets you customize bankroll amount and other settings
- Shows market analysis before finalizing config
- Saves the generated config to a file

**Why it's valuable:**
- **User-friendly**: Perfect for beginners who are unfamiliar with PM4
- **Guided**: Holds your hand through each configuration step
- **Validation**: Double-checks your inputs and market suitability
- **Educational**: Explains each parameter as you configure it

**Example workflow:**
```
Wizard: "Paste your Polymarket market URL:"
You: "https://polymarket.com/market/ethereum-above-5000-end-of-2025"
Wizard: [Analyzes market...] "This looks good! Set your bankroll:"
You: "100"
Wizard: "Config saved as config_generated.json"
```

#### **Tool Integration Benefits**

**Before these tools:** Manual process taking 30-60 minutes
1. Browse Polymarket website manually
2. Guess at market suitability based on visual inspection
3. Manually extract condition IDs from developer tools
4. Manually convert dates to timestamps
5. Manually create config.json with trial-and-error parameter tuning

**After these tools:** Automated process taking 5 minutes
1. Run market analyzer → Get objective suitability score
2. Run config helper → Get complete, validated config file
3. Proceed to calibration with confidence

**Safety improvements:**
- Eliminates unsuitable markets before configuration
- Prevents configuration errors (wrong IDs, bad timestamps)
- Ensures proper parameter ranges for testing
- Validates market has sufficient liquidity for PM4

### Configuration File
Ensure your `config.json` has appropriate risk settings for testing:

```json
{
  "market": {
    "market": "0x_CONDITION_ID",
    "asset_id_yes": "0x_YES_TOKEN_ID",
    "asset_id_no": "0x_NO_TOKEN_ID",
    "start_ts_ms": 1710000000000,
    "resolve_ts_ms": 1720000000000
  },
  "risk": {
    "bankroll_B": 100.0,  // Start with small amount for testing
    "n_plays": 1,          // Single market for focused testing
    "gamma_max": 10.0      // Conservative spreads
  },
  "warmup": {
    "min_return_samples": 360,  // ~30 minutes of data
    "max_warmup_s": 3600         // 1 hour timeout
  }
}
```

---

## 🚀 **Step-by-Step Dry Run Process**

### **Step 1: Select a Test Market on Polymarket**

**Time Estimate**: 5-10 minutes

#### **Option A: Manual Market Selection**

#### 1.1 Navigate to Polymarket
- Open [https://polymarket.com](https://polymarket.com) in your browser
- Ensure you're logged in to your account

#### 1.2 Choose Market Type Carefully
**Select from these categories:**
- **Politics** (recommended for beginners)
- **Sports** (good volatility)
- **Crypto** (high volatility - advanced)
- **Economics** (moderate volatility)

**Avoid:**
- ❌ Very short-term markets (< 24 hours)
- ❌ Extremely low volume markets
- ❌ Markets with < $10k total volume
- ❌ Markets that resolve today

#### 1.3 Evaluate Market Suitability

**Check these indicators:**

**Volume & Liquidity:**
- Look for "Volume" > $50k in the last 24h
- Check "Active Markets" count
- Prefer markets with 100+ active traders

**Price Action:**
- Mid price should be between 0.10 and 0.90 (avoid extremes)
- Avoid markets that haven't moved in 2+ hours
- Look for recent price movement (last hour)

**Time to Resolution:**
- Should be 1+ weeks away (not days)
- Markets resolving within 24 hours are too risky

**Example Good Market:**
```
Market: "Will Ethereum reach $10k before 2025?"
Volume: $125k (24h)
Liquidity: High
Mid Price: 0.35
Time Left: 8 months
```

#### 1.4 Extract Market Information

**From Polymarket URL:**
```
https://polymarket.com/market/ethereum-to-10k-before-2025
```

**You need:**
- **Condition ID**: The long hex string in the URL
- **Yes Token ID**: Click "Yes" outcome → get contract address
- **No Token ID**: Click "No" outcome → get contract address
- **Resolve Date**: Market resolution date

**Update your `config.json`:**
```json
{
  "market": {
    "market": "0x0123456789abcdef...",
    "asset_id_yes": "0xabcdef1234567890...",
    "asset_id_no": "0xfedcba9876543210...",
    "start_ts_ms": 1700000000000,
    "resolve_ts_ms": 1735000000000
  }
}
```

#### **Option B: Automated Market Analysis (Recommended)**

Use PM4's built-in market analyzer for objective evaluation:

```bash
# Analyze a specific market
python -m pm4.market_analyzer "ethereum-to-10k-before-2025"
```

**Example Output:**
```
==================================================
MARKET ANALYSIS: ethereum-to-10k-before-2025
==================================================
Condition ID: 0x1234567890abcdef
Current Price: 0.350
24h Volume: $125,430
Active Traders: 234
Last Trade: 0.8 hours ago
Time to Resolution: 245 days
Price Range (24h): 0.330 - 0.380

RECOMMENDATION: RECOMMENDED

DETAILED ANALYSIS:
  ✓ Excellent volume: $125,430
  ✓ High trader count: 234
  ✓ Moderate time horizon: 245 days
  ✓ Price in good range: 0.35

✅ SUITABLE FOR PM4 MARKET MAKING
  Proceed with warmup and dry-run testing
==================================================
```

**Automated Config Generation:**
```bash
# Generate config template automatically
python -m pm4.market_config_helper "https://polymarket.com/market/ethereum-to-10k-before-2025"
```

---

### **Step 2: Run Warmup Calibration**

**Time Estimate**: 30-45 minutes

#### 2.1 Start Calibration
```bash
python -m pm4.warmup config.json
```

**What happens:**
- Connects to Polymarket WebSocket
- Collects 360 price samples (30 minutes minimum)
- Calculates volatility metrics
- Generates human-readable report

#### 2.2 Monitor Progress
You should see output like:
```
--- Starting Warmup for 3600.0s ---
Goal: Collect 360 return samples.
Sample interval: 5.0s

Progress: 45/360 samples (12.5%) | Current Sigma: 1.15 | Elapsed: 3m 45s
```

#### 2.3 Analyze Warmup Report
When complete, you'll see:

```
========================================
CALIBRATION REPORT
========================================
Samples Collected: 360 / 360
Collection Time: 30m 15s
Base Volatility (MAD): 0.0823
Shock Factor (EMA Fast/Slow): 0.120 / 0.098

Volatility Interpretation:
  Current Sigma: 1.15x baseline
  Verdict: MODERATE VOLATILITY

Market Conditions:
  - Price Range: 0.45 - 0.55
  - Average Spread: 0.02
  - Trade Rate: 0.12 trades/sec

Sanity Checks:
  ✓ Sigma in reasonable range (1.0 - 2.0)
  ✓ Sufficient samples collected
  ⚠ EMA fast > EMA slow (increasing volatility detected)

Saved to: ./data/warm_calibration.json
```

#### 2.4 Validate Calibration Data

**Check these values:**

**Sigma (Volatility Multiplier):**
- **1.0 - 2.0**: ✅ Normal market conditions
- **< 0.8**: ⚠️ Too low (might indicate data issues)
- **> 3.0**: ⚠️ Too high (extremely volatile market)

**Sample Count:**
- **Must be ≥ 360** ✅
- If less, calibration period was too short

**EMA Values:**
- **Fast ≈ Slow**: Stable market
- **Fast > Slow**: Increasing volatility
- **Fast < Slow**: Decreasing volatility

**Trade Rate:**
- **> 0.05**: Good liquidity
- **< 0.01**: Poor liquidity (consider different market)

**❌ Stop Here If:**
- Sigma > 2.5 (market too volatile)
- Samples < 360 (insufficient data)
- Trade rate < 0.01 (illiquid market)

---

### **Step 3: Run Dry-Run Mode**

**Time Estimate**: 5-10 minutes

#### 3.1 Start Dry-Run
```bash
python -m pm4.run_bot config.json --dry-run
```

**What happens:**
- Loads calibration data from previous step
- Connects to live market data
- Calculates theoretical quotes every 2 seconds
- **Prints but does NOT place orders**

#### 3.2 Monitor Dry-Run Output
You should see output like:
```
⚠️  DRY RUN MODE ACTIVE ⚠️
No orders will be placed. Watching market and printing theoretical quotes...
========================================

[2024-12-29 14:30:15] p=0.480 q=0.0 sig=1.15 r=-0.042 n_bids=3 n_asks=3
[DRY] WOULD PLACE BUY: 25.0 @ 0.475 (order_id: dry_run_BUY_0x123_4750)
[DRY] WOULD PLACE BUY: 20.0 @ 0.465 (order_id: dry_run_BUY_0x123_4650)
[DRY] WOULD PLACE SELL: 25.0 @ 0.485 (order_id: dry_run_SELL_0x456_4850)
[DRY] WOULD PLACE SELL: 20.0 @ 0.495 (order_id: dry_run_SELL_0x456_4950)
```

#### 3.3 Compare with Live Market

**Open Polymarket in browser** and compare:

**Your Bot Quotes:**
```
BUY @ 0.475, 0.465
SELL @ 0.485, 0.495
Mid Price: (0.475 + 0.485) / 2 = 0.480
```

**Live Market (Polymarket):**
```
Best Bid: 0.47
Best Ask: 0.49
Market Mid: 0.48
```

---

### **Step 4: Manual Sanity Checks**

**Time Estimate**: 5 minutes

#### 4.1 Spread Analysis

**Calculate your spread:**
```
Your Spread = Best Ask - Best Bid = 0.485 - 0.475 = 0.010 (1%)
Market Spread = 0.49 - 0.47 = 0.020 (2%)
```

**Acceptable Ranges:**
- ✅ **Your spread ≤ Market spread**: You're not crossing the market
- ✅ **Your spread ≤ 3%**: Not too wide (would lose to market makers)
- ❌ **Your spread > Market spread**: You're too aggressive
- ❌ **Your spread > 5%**: Too conservative

#### 4.2 Position Size Validation

**Check order sizes:**
- Should be reasonable (not 0.01 or 10000.0)
- Should decrease with distance from mid price
- BUY sizes should equal SELL sizes (symmetric)

**Example Good Sizing:**
```
BUY: 25.0 @ 0.475    (close to mid)
BUY: 20.0 @ 0.465    (farther, smaller size)
SELL: 25.0 @ 0.485   (close to mid)
SELL: 20.0 @ 0.495   (farther, smaller size)
```

#### 4.3 Price Logic Verification

**Your quotes should:**
- ✅ **BUY prices < Current mid price**
- ✅ **SELL prices > Current mid price**
- ✅ **Prices decrease as you go deeper (BUY side)**
- ✅ **Prices increase as you go deeper (SELL side)**

#### 4.4 Mathematical Consistency

**Verify Kelly Criterion:**
- Position sizes should be proportional to edge
- Larger positions on side with better odds
- Time decay should reduce sizes as resolution approaches

---

### **Step 5: Risk Management Validation**

**Time Estimate**: 3 minutes

#### 5.1 Inventory Impact

**Check qhat values in logs:**
```
qhat = -0.1 (slightly short)
```

**Acceptable ranges:**
- ✅ **|qhat| < 0.3**: Low inventory risk
- ✅ **|qhat| < 0.5**: Moderate risk
- ❌ **|qhat| > 0.8**: High inventory risk (reduce position)

#### 5.2 Gamma Scaling

**Check gamma values:**
```
gamma = 1.15
```

**Interpretation:**
- **1.0**: Neutral position
- **1.0-2.0**: Normal position with wider spreads
- **> 2.0**: Large position requiring much wider spreads

#### 5.3 Sigma Multiplier

**Check sigma values:**
```
sigma = 1.15
```

**Market volatility adjustment:**
- **1.0**: Baseline volatility
- **1.0-1.5**: Normal market conditions
- **> 2.0**: High volatility requiring conservative sizing

---

### **Step 6: Real-World Alignment Test**

**Time Estimate**: 5 minutes

#### 6.1 Observe Market Behavior

**During dry-run, watch:**
- How quickly prices change
- Trading frequency
- Bid/ask spread movements
- Large order flow

#### 6.2 Simulate Market Impact

**Mental calculation:**
- If your orders went live, how much would they move the market?
- Are you providing meaningful liquidity or just noise?

#### 6.3 Time-Based Risk Assessment

**Calculate time factor:**
```
Time remaining: 8 months = ~240 days
Total market duration: ~300 days
Time factor = (240/300)^0.5 ≈ 0.89 (89% of full size)
```

**Should reduce position sizes for markets close to resolution.**

---

### **Step 7: Go/No-Go Decision**

**Time Estimate**: 2 minutes

#### ✅ **GO Criteria (All must be true):**

1. **Calibration**: Sigma 1.0-2.0, 360+ samples
2. **Dry-Run**: Quotes look reasonable vs market
3. **Sanity**: Spreads ≤ market spread, logical pricing
4. **Risk**: |qhat| < 0.5, gamma < 2.0
5. **Market**: Sufficient liquidity and time

#### ❌ **NO-GO Criteria (Any true = stop):**

1. **Sigma > 2.5**: Market too volatile
2. **Your spread > market spread**: Too aggressive
3. **Position sizes unreasonable**: Too big/small
4. **Pricing errors**: BUY > SELL prices
5. **Poor liquidity**: < 0.01 trades/sec

#### 🚨 **Emergency Stops:**

- **Immediate shutdown** if quotes seem wrong
- **Never** go live with questionable calibration
- **Start small** even when going live (reduce bankroll)

---

### **Step 8: Live Trading (If Approved)**

**Only proceed if all checks pass:**

```bash
# Start with small position limits
python -m pm4.run_bot config.json
```

**Monitor closely for first 30 minutes:**
- Position changes
- P&L evolution
- Order execution
- Market impact

---

## 🛠️ **Troubleshooting Guide**

### **Common Issues**

#### **"No calibration file found"**
```
❌ Error: Calibration file not found: ./data/warm_calibration.json
```
**Solution:** Run warmup first: `python -m pm4.warmup config.json`

#### **Poor Calibration**
```
Sigma: 3.5 (VERY HIGH VOLATILITY)
```
**Solution:** Choose different market or wait for calmer conditions

#### **No Quotes Generated**
```
[2024-12-29 14:30:15] p=0.480 q=0.0 sig=1.15 r=-0.042 n_bids=0 n_asks=0
```
**Solution:** Check risk parameters or market conditions

#### **Unrealistic Order Sizes**
```
[DRY] WOULD PLACE BUY: 10000.0 @ 0.475
```
**Solution:** Reduce bankroll_B in config or check Kelly calculations

### **Debug Mode**
```bash
# Enable detailed logging
export PYTHONPATH=/path/to/pm4
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
# Then run your commands
"
```

---

## 📊 **Expected Results**

### **Good Dry-Run Example**
```
Market: Moderate volatility political market
Your Spread: 1.2%
Market Spread: 2.1%
Position: Small (qhat = 0.15)
Sigma: 1.25
Trade Rate: 0.08/sec
✅ SAFE TO GO LIVE
```

### **Bad Dry-Run Example**
```
Market: Extreme volatility crypto market
Your Spread: 3.5%
Market Spread: 1.8%
Sigma: 3.8
Trade Rate: 0.002/sec
❌ DO NOT GO LIVE
```

---

## 🎯 **Key Takeaways**

1. **Never skip dry-run** - 10 minutes of validation prevents costly mistakes
2. **Trust your math** - If numbers look wrong, they probably are
3. **Start small** - Better to make $10 than lose $1000
4. **Monitor continuously** - Markets change, your bot should adapt
5. **Human oversight** - You're responsible for the final go/no-go decision

**Remember**: This is high-frequency trading with real risk. The dry-run process exists to give you confidence in your model's behavior before risking capital.

---

*Last updated: December 29, 2024*
