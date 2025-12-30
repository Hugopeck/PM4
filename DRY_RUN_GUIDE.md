# PM4 Automated Market Analysis & Dry-Run Guide

## 🎯 **Purpose**

This guide shows you how to use PM4's **automated market analysis tools** for safe, data-driven market making. Instead of manual market evaluation, you'll use three powerful tools:

1. **`market_analyzer`** - Analyzes market suitability objectively
2. **`market_config_helper`** - Generates complete configurations automatically
3. **`dry-run workflow`** - Validates your setup before going live

**Result**: From market discovery to live trading in under 10 minutes with complete safety validation.

---

## 📋 **Prerequisites**

### Python Environment Setup

**First, ensure you're in the correct directory and have dependencies installed:**

```bash
# Navigate to PM4 project (note: capital PM4)
cd /Users/hugopeck/PM4

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies (if not already done)
pip install -r requirements.txt

# Verify installation
python -m pm4.market_analyzer --help
```

**Note:** On macOS, if `python` doesn't work, use `python3` or activate the venv first.

### Environment Variables Setup
```bash
# Set your Polymarket credentials (required for all tools)
export PK="your_private_key_here"
export CLOB_API_KEY="your_api_key"          # Optional but recommended
export CLOB_SECRET="your_api_secret"        # Optional but recommended
export CLOB_PASS_PHRASE="your_passphrase"    # Optional but recommended
export FUNDER_ADDRESS="your_funder_address"  # Optional for gasless trading
```

### PM4 Analysis Tools Overview

PM4 provides **three automated tools** that transform manual market analysis into a 5-minute automated process:

| Tool | Purpose | Input | Output |
|------|---------|-------|--------|
| `market_analyzer` | **Market Evaluation** | URL or slug | Suitability score + recommendation |
| `market_config_helper` *(CLI)* | **Config Generation** | URL + options | Complete config.json file |
| `market_config_helper --interactive` | **Guided Setup** | Interactive prompts | Step-by-step config creation |

---

## 🛠️ **Tool Details & Usage**

### **1. Market Analyzer (`pm4.market_analyzer`)**

**Purpose**: Objectively evaluates if a market is suitable for PM4 trading.

**Usage:**
```bash
# Analyze any Polymarket market
python -m pm4.market_analyzer "https://polymarket.com/market/will-ethereum-reach-10k-before-2025"

# Or use just the slug (both work!)
python -m pm4.market_analyzer "will-ethereum-reach-10k-before-2025"
```

**What it analyzes:**
- 📊 **Volume**: 24h trading volume ($50k+ recommended)
- 👥 **Traders**: Active participants (100+ recommended)
- ⏰ **Activity**: Recent trades (within 2 hours preferred)
- 📅 **Time Horizon**: Days until resolution (30+ days preferred)
- 💰 **Price Position**: Current price vs extremes (0.15-0.85 preferred)

**Scoring System:**
- **RECOMMENDED** (5-7 points): Safe for PM4 trading
- **CONDITIONAL** (3-4 points): May work with caution
- **NOT RECOMMENDED** (0-2 points): Avoid this market

**Example Output:**
```
Analyzing market: will-ethereum-reach-10k-before-2025
==================================================
MARKET ANALYSIS: will-ethereum-reach-10k-before-2025
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
```

### **2. Market Config Helper CLI (`pm4.market_config_helper`)**

**Purpose**: Generates complete PM4 configuration files from Polymarket URLs.

**CLI Tool Features:**
- ✅ **Command-line interface** with multiple modes
- ✅ **URL parsing** from Polymarket links
- ✅ **Interactive mode** for guided setup
- ✅ **Configurable output** and parameters
- ✅ **Batch processing** capabilities

**Usage:**
```bash
# Generate config from URL with default settings
python -m pm4.market_config_helper "https://polymarket.com/market/will-ethereum-reach-10k-before-2025"

# Customize bankroll amount
python -m pm4.market_config_helper "https://polymarket.com/market/will-ethereum-reach-10k-before-2025" --bankroll 100

# Specify output file
python -m pm4.market_config_helper "https://polymarket.com/market/market-name" --output my_config.json
```

**What it does:**
1. **URL Parsing**: Extracts market slug from any Polymarket URL
2. **Market Analysis**: Runs the analyzer to validate suitability
3. **Config Generation**: Creates complete `config.json` with:
   - Market condition ID (auto-detected)
   - Asset IDs (placeholder - you'll need to fill from market page)
   - Proper timestamps (placeholder - you'll need to set actual dates)
   - Safe default parameters for testing
   - Market analysis summary embedded

**Example Output:**
```
Analyzing market: will-ethereum-reach-10k-before-2025
✓ Configuration saved to: config_generated.json

Market Summary:
  Volume: $125,430
  Traders: 234
  Price: 0.350
  Status: RECOMMENDED
```

### **3. Interactive Config Helper (`pm4.market_config_helper --interactive`)**

**Purpose**: Guided, step-by-step configuration for beginners.

**Usage:**
```bash
# Start the interactive wizard
python -m pm4.market_config_helper --interactive
```

**What it does:**
1. **URL Input**: Prompts you to paste a Polymarket URL
2. **Validation**: Checks URL format and extracts market data
3. **Market Analysis**: Shows suitability analysis before proceeding
4. **Customization**: Lets you set bankroll and other parameters
5. **File Generation**: Creates `config_generated.json` with all settings

**Example Interactive Session:**
```
PM4 Market Configuration Helper
========================================

Enter Polymarket market URL: https://polymarket.com/market/will-ethereum-reach-10k-before-2025
✓ Extracted market slug: will-ethereum-reach-10k-before-2025

Analyzing market: will-ethereum-reach-10k-before-2025

Market Analysis:
  Volume (24h): $125,430
  Active Traders: 234
  Current Price: 0.350
  Recommendation: RECOMMENDED

Enter bankroll amount (USD) [50]: 100

✓ Configuration saved to: config_generated.json

Next steps:
1. Edit the generated config file
2. Fill in the asset IDs from Polymarket market page
3. Set correct start_ts_ms and resolve_ts_ms dates
4. Rename to config.json and run: python -m pm4.warmup config.json
```

---

---

## 🚀 **Automated 5-Minute Setup & Dry-Run Process**

### **Step 1: Automated Market Discovery & Analysis**

**Time Estimate**: 30 seconds

Use PM4's market analyzer to automatically evaluate market suitability:

```bash
# Find a good market URL from Polymarket and analyze it
python -m pm4.market_analyzer "https://polymarket.com/market/will-ethereum-reach-10k-before-2025"
```

**What happens automatically:**
- ✅ **Volume Check**: Validates 24h volume > $50k
- ✅ **Trader Activity**: Confirms 100+ active participants
- ✅ **Recent Movement**: Ensures market traded within 2 hours
- ✅ **Time Horizon**: Verifies 30+ days until resolution
- ✅ **Price Position**: Checks price between 0.15-0.85

**Expected Output:**
```
Analyzing market: will-ethereum-reach-10k-before-2025
==================================================
RECOMMENDATION: RECOMMENDED
✅ SUITABLE FOR PM4 MARKET MAKING
==================================================
```

**❌ If NOT RECOMMENDED:**
- Choose a different market from Polymarket
- Look for markets with higher volume/trader counts
- Avoid markets resolving within 24 hours

### **Step 2: Automated Configuration Generation**

**Time Estimate**: 30 seconds

Generate a complete PM4 configuration automatically:

```bash
# Use the same URL to generate config
python -m pm4.market_config_helper "https://polymarket.com/market/will-ethereum-reach-10k-before-2025"
```

**What gets created:**
- ✅ **Market IDs**: Auto-extracted condition ID
- ✅ **Safe Defaults**: Conservative parameters for testing
- ✅ **Analysis Embedded**: Market suitability data included
- ✅ **Complete Config**: Ready for PM4 warmup

**Output:**
```
✓ Configuration saved to: config_generated.json

Market Summary:
  Volume: $125,430
  Traders: 234
  Price: 0.350
  Status: RECOMMENDED
```

### **Step 3: Automated Config Finalization**

**Time Estimate**: 30 seconds

The generated configuration is automatically populated with:
- ✅ **Condition ID**: Extracted from Polymarket API
- ✅ **Token IDs**: YES/NO token IDs from API response
- ✅ **Timestamps**: Start and resolution dates converted automatically
- ✅ **Bankroll**: Safe default ($50) or your custom amount

**Review the generated config:**
```bash
# Quick review (optional)
cat config_generated.json | jq '.market'
```

**Rename and proceed:**
```bash
mv config_generated.json config.json
```

**Note**: All required fields are automatically filled from the Polymarket API. Only review if you want to adjust risk parameters or bankroll.

### **Step 4: Automated Calibration (Warmup)**

**Time Estimate**: 10-15 minutes

Run PM4's three-phase warmup to calibrate risk parameters:

```bash
# Start three-phase calibration with your config
python -m pm4.warmup config.json
```

**Three-Phase Process:**
**Phase 1: Observation (5-10 minutes)**
- Fast sampling (1s intervals) to analyze market activity patterns
- Collects price change frequencies and trade inter-arrival times
- Measures autocorrelation and volatility clustering characteristics

**Phase 2: Meta-Calibration (30 seconds)**
- Analyzes observed activity to optimize warmup parameters
- Calculates optimal `dt_sample_s`, `tau_fast_s`, `tau_slow_s`, markout horizons
- Saves meta-calibration to `meta_warmup_params.json`

**Phase 3: Calibration (5-10 minutes)**
- Uses meta-calibrated parameters to collect 360+ return samples
- Applies optimized EMA time constants and sampling intervals
- Generates comprehensive calibration report

**What happens automatically:**
- ✅ **Activity Analysis**: Measures market microstructure and trading patterns
- ✅ **Parameter Optimization**: Self-tunes warmup parameters for market conditions
- ✅ **Data Collection**: Gathers 360+ price samples with optimized settings
- ✅ **Risk Calibration**: Calculates volatility and market parameters
- ✅ **Validation**: Ensures sufficient data quality
- ✅ **Report Generation**: Human-readable calibration summary with meta-calibration details

**Expected Output:**
```
--- Starting Warmup for 3600.0s ---
Phase 1: Observation (collecting market activity data)
Phase 2: Meta-calibrating warmup parameters...
✓ Phase 2 complete: Meta-calibration applied
Phase 3: Collecting return samples with calibrated parameters...

Progress: 360/360 samples | Current Sigma: 1.15 | Elapsed: 32m 15s

========================================
CALIBRATION REPORT
========================================
Samples Collected: 360 / 360
Collection Time: 30m 15s
Base Volatility (MAD): 0.0823
Shock Factor (EMA Fast/Slow): 0.120 / 0.098

Meta-Calibration Applied:
  dt_sample_s: 4.2
  tau_fast_s: 25.0
  tau_slow_s: 1650.0
  markout_h1_s: 8.5
  markout_h2_s: 45.0

Market Activity Observed:
  - Price Changes: 245
  - Median Price Interval: 4.2s
  - Trade Interarrivals: 180
  - Median Trade Interval: 10.5s
  - Autocorr Half-Life: 25.0s
  - Vol Cluster Timescale: 1650.0s

Volatility Interpretation:
  Current Sigma: 1.15x baseline
  Verdict: MODERATE VOLATILITY

Saved calibration to: ./data/warm_calibration.json
```

### **Step 5: Dry-Run Validation**

**Time Estimate**: 2 minutes

Test your setup without risking real capital:

```bash
# Start dry-run mode (NO ORDERS WILL BE PLACED)
python -m pm4.run_bot config.json --dry-run
```

**What happens:**
- ✅ **Live Data Connection**: Connects to real market data
- ✅ **Quote Generation**: Calculates theoretical bid/ask prices
- ✅ **Safety Mode**: Prints quotes but does NOT place orders
- ✅ **Real-time Validation**: Shows how your bot would behave

**Expected Output:**
```
⚠️  DRY RUN MODE ACTIVE ⚠️
No orders will be placed. Watching market and printing theoretical quotes...

[DRY] WOULD PLACE BUY: 25.0 @ 0.475 (order_id: dry_run_BUY_0x123_4750)
[DRY] WOULD PLACE SELL: 25.0 @ 0.485 (order_id: dry_run_SELL_0x456_4850)
```

### **Step 6: Go/No-Go Decision**

**Time Estimate**: 1 minute

**✅ SAFE TO GO LIVE if:**
- Meta-calibration completed successfully (shows market activity analysis)
- Calibration completed successfully (360+ samples)
- Dry-run shows reasonable quotes (not too wide, logical pricing)
- Market analysis was "RECOMMENDED"
- Meta-calibration parameters look reasonable for market conditions

**❌ DO NOT GO LIVE if:**
- Meta-calibration failed (using config defaults only)
- Calibration failed or shows extreme volatility
- Dry-run quotes seem wrong (spreads too wide, illogical prices)
- Market analysis was "NOT RECOMMENDED"
- Meta-calibration shows extreme parameter values

### **Step 7: Live Trading (If Approved)**

**Only proceed if all checks pass:**

```bash
# Start with conservative settings for first few hours
python -m pm4.run_bot config.json
```

**Monitor closely:**
- Position changes
- P&L evolution
- Order execution success
- Market impact

---

## 🛠️ **Troubleshooting Guide**

### **Setup & Installation Issues**

#### **"ModuleNotFoundError: No module named 'requests'"**
```bash
❌ ModuleNotFoundError: No module named 'requests'
```
**Solution:** Activate the virtual environment and install dependencies:
```bash
# Navigate to PM4 project directory (note: capital PM4, not lowercase pm4)
cd /Users/hugopeck/PM4

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Now try again
python -m pm4.market_analyzer "https://polymarket.com/market/market-name"
```

#### **"command not found: python"**
```bash
❌ zsh: command not found: python
```
**Solution:** Use `python3` on macOS, or activate venv:
```bash
# Option 1: Use python3 directly
python3 -m pm4.market_analyzer "url"

# Option 2: Activate venv (recommended)
source venv/bin/activate
python -m pm4.market_analyzer "url"
```

#### **"command not found: -m"**
```bash
❌ zsh: command not found: -m
```
**Solution:** You forgot `python` before `-m`:
```bash
# Wrong:
-m pm4.market_analyzer "url"

# Correct:
python -m pm4.market_analyzer "url"
# or with venv activated:
source venv/bin/activate
python -m pm4.market_analyzer "url"
```

#### **Wrong Directory**
```bash
# If you're in lowercase 'pm4' directory instead of 'PM4'
cd /Users/hugopeck/PM4  # Note: capital letters
source venv/bin/activate
```

### **Common Issues**

#### **"No calibration file found"**
```bash
❌ Error: Calibration file not found: ./data/warm_calibration.json
```
**Solution:** Run warmup first: `python -m pm4.warmup config.json`

#### **Market Not Recommended**
```
RECOMMENDATION: NOT_RECOMMENDED
```
**Solution:** Choose a different market with higher volume/activity

#### **Poor Calibration Quality**
```
Samples Collected: 180 / 360
```
**Solution:** Market may be too illiquid - try a different market

#### **Unrealistic Quotes in Dry-Run**
```
[DRY] WOULD PLACE BUY: 10000.0 @ 0.475
```
**Solution:** Check bankroll settings and risk parameters

### **Tool-Specific Help**

#### **Market Analyzer Issues**
```bash
# If analysis fails
python -m pm4.market_analyzer "https://polymarket.com/market/market-name" --verbose
```

#### **Config Helper Issues**
```bash
# Force overwrite existing config
python -m pm4.market_config_helper "url" --output config.json --force
```

#### **Interactive Mode Issues**
```bash
# Skip analysis in interactive mode
python -m pm4.market_config_helper --interactive --skip-analysis
```

---

## 📊 **Success Metrics**

### **Good Automated Setup**
```
✅ Market Analysis: RECOMMENDED
✅ Config Generation: Successful
✅ Calibration: 360+ samples, sigma 1.0-2.0
✅ Dry-Run: Quotes look reasonable
✅ Live Trading: Smooth execution
```

### **Time Breakdown**
- Market Analysis: 30 seconds
- Config Generation: 30 seconds
- Config Review: 2 minutes
- Calibration: 5-10 minutes
- Dry-Run: 2 minutes
- **Total**: ~10-15 minutes

### **Risk Reduction Achieved**
- ❌ Manual market evaluation errors → ✅ Automated scoring
- ❌ Configuration mistakes → ✅ Generated templates
- ❌ Suboptimal warmup parameters → ✅ Meta-calibrated settings
- ❌ Poor calibration → ✅ Quality validation + activity-based optimization
- ❌ Live trading surprises → ✅ Dry-run testing

---

## 🎯 **Key Takeaways**

1. **Use the tools in order**: Analyzer → Config Helper → Warmup → Dry-run → Live
2. **Trust automated analysis**: The tools know more about market suitability than guesswork
3. **Meta-calibration matters**: Three-phase warmup optimizes parameters for each market's activity patterns
4. **Never skip dry-run**: 2 minutes of validation prevents costly mistakes
5. **Start small**: Even with good analysis, begin with conservative settings
6. **Monitor continuously**: Markets change - PM4 adapts parameters automatically during trading

**The automated workflow, enhanced by meta-calibration, transforms hours of manual work into a 10-minute process with superior safety, reliability, and market-specific optimization.**

---

*Last updated: December 29, 2024*

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
# Generate complete config automatically with all fields auto-filled
python -m pm4.market_config_helper "https://polymarket.com/market/ethereum-to-10k-before-2025"
```

The config helper automatically extracts:
- ✅ Condition ID from API
- ✅ YES/NO Token IDs from API  
- ✅ Start and resolution timestamps from API dates
- ✅ Market analysis data embedded in config

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

**Meta-Calibration Parameters:**
- **dt_sample_s**: Should match observed price change frequency (typically 1-10s)
- **tau_fast_s**: Should reflect autocorrelation timescale (typically 10-60s)
- **tau_slow_s**: Should be much longer than tau_fast (typically 600-3600s)
- **markout_h1_s/markout_h2_s**: Should align with trade frequency

**Sigma (Volatility Multiplier):**
- **1.0 - 2.0**: ✅ Normal market conditions
- **< 0.8**: ⚠️ Too low (might indicate data issues)
- **> 3.0**: ⚠️ Too high (extremely volatile market)

**Sample Count:**
- **Must be ≥ 360** ✅
- If less, calibration period was too short

**Market Activity Metrics:**
- **Price Changes**: ≥ 50 for reliable meta-calibration
- **Trade Interarrivals**: ≥ 20 for markout horizon optimization
- **Autocorr Half-Life**: Reasonable timescale (not too short/long)

**EMA Values:**
- **Fast ≈ Slow**: Stable market
- **Fast > Slow**: Increasing volatility
- **Fast < Slow**: Decreasing volatility

**Trade Rate:**
- **> 0.05**: Good liquidity
- **< 0.01**: Poor liquidity (consider different market)

**❌ Stop Here If:**
- Meta-calibration failed (using config defaults)
- Sigma > 2.5 (market too volatile)
- Samples < 360 (insufficient data)
- Trade rate < 0.01 (illiquid market)
- Meta-calibration shows extreme parameter values

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
