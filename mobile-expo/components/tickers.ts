// mobile-expo/components/tickers.ts

// Small default list (fast + friendly for new users)
export const STARTER_TICKERS: string[] = [
  "SPY", "QQQ", "IWM",
  "AAPL", "MSFT", "AMZN", "NVDA", "TSLA",
  "META", "NFLX", "AMD"
];

// Bigger visible catalog (for pickers + discovery).
// This does NOT mean the app runs all of them.
// It only runs the tickers the user selects.
export const CATALOG_TICKERS: string[] = [
  "AMZN","META","TSLA","NVDA","NFLX","AMD","INTC","JPM","BAC","GS",
  "MS","XOM","CVX","SPY","QQQ","DIA","ORCL","IBM","CRM","ADBE","WMT",
  "COST","HD","PFE","JNJ","UNH","BA","CAT","GE","XLK","XLF","XLE",
  "XLV","XLI","XLY","XLP","XLU"
];
