import json
import datetime as dt
import pandas as pd
import os
import fxcmpy
from statsmodels.tsa.arima_model import ARIMA
import warnings

def load_full_df(ticker, interval):
    startTime = dt.datetime.now().timestamp()
    final_call = False
    total_period_seconds = interval_seconds*9000
    start = dt.datetime(2018,1,1)
    end = start + dt.timedelta(seconds=total_period_seconds)
    df = pd.DataFrame()
    while True:
        new_df = con.get_candles(instrument=ticker, period=interval, start=start, end=end,number=10000)
        df = df.append(new_df)
        if final_call:
            break
        start = end
        end = start + dt.timedelta(seconds=total_period_seconds)
        if end > dt.datetime.now():
            final_call = True
            end = dt.datetime.now()
    df = df.reset_index().drop_duplicates(subset='date', keep='first').set_index('date')
    endTime = dt.datetime.now().timestamp()
    print(f"Took {endTime - startTime} seconds to load full DataFrame.")
    return df

if __name__ == "__main__":
    # CONFIGURABLE SETTINGS
    arima_order = (5,1,0)
    training_data_intervals = 10000

    # DEFAULT SETTINGS
    warnings.filterwarnings('ignore', 'statsmodels.tsa.arima_model.ARMA',
                        FutureWarning)
    warnings.filterwarnings('ignore', 'statsmodels.tsa.arima_model.ARIMA',
                        FutureWarning)
    with open('APISettings.json','r') as f:
        config = json.load(f)
    # CREATE DEFAULT VARS
    period_to_seconds = {"m5":300,"m15":900,"H1":3600}
    one_pip = 0.0001
    all_results = list()
    # DEFAULT CONFIG LOAD
    access_token = config["access_token"]
    account_id = config["account_id"]
    account_type = config["account_type"]
    interval = config["interval"]
    max_trade_open_time = config["max_trade_open_time"]
    ticker = config["ticker"]
    ticker_file = ticker.replace("/","")
    auto_trade = config["auto_trade"]
    trade_margin = config["trade_margin"]
    next_interval = None
    interval_seconds = period_to_seconds[interval]

    # CONNECT TO FXCM
    con = fxcmpy.fxcmpy(access_token=access_token, server=account_type)
    print("Generated Default configs and established a connection to FXCM.")

    # CREATE DEFAULT FOLDERS AND FILES IF THEY DONT EXIST
    if not os.path.exists("Backtesting"):
        os.mkdir("Backtesting")
    if not os.path.exists(f"Backtesting\\{ticker_file}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_intervals_{str(training_data_intervals)}.json"):
        with open(f"Backtesting\\{ticker_file}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_intervals_{str(training_data_intervals)}.json","w") as f:
            json.dump({},f)
    if not os.path.exists(f"Backtesting\\{ticker_file}_{interval}_price_log.json"):
        print("Loading full DataFrame.")
        df = load_full_df(ticker, interval)
        df.index = df.index.astype(str)
        df.rename(columns={"askclose":"close", "askhigh":"high", "asklow":"low"},inplace=True)
        df.drop(["bidopen","bidclose","bidhigh","bidlow","askopen","tickqty"],axis=1,inplace=True)
        json_string = df.to_json(orient="index")
        new_json_data = json.loads(json_string)
        with open(f"Backtesting\\{ticker_file}_{interval}_price_log.json","w")as f:
            json.dump(new_json_data,f,indent=2,sort_keys=True)
    # lOAD THE BACKTESTING DATA IF IT EXISTS
    all_data = pd.read_json(f"Backtesting\\{ticker_file}_{interval}_price_log.json", orient="index", convert_dates=False)
    print(f"Loaded initial backtesting dataframe of {len(all_data)} values.")

    # GET CLOSE VALUES
    x = all_data["close"].values.tolist()
    # GET DATES
    dates = all_data.index.values.tolist()

    # OPEN TRADE LOG
    with open(f"Backtesting\\{ticker_file}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_intervals_{str(training_data_intervals)}.json","r") as f:
        trade_log = json.load(f)

    # START RUNNING PREDICTIONS
    for n in range(len(all_data)):
        print(f"{n}/{len(all_data)}")
        e = training_data_intervals + n
        x_train = x[n:e]
        previous_close = x[e]
        date = dates[e+1]
        actual_close = x[e+1]
        model = ARIMA(x_train, order=(5,1,0))
        model_fit = model.fit(disp=0)
        output = model_fit.forecast()
        result = output[0][0]

        # CALC VALUE IN PIPS
        pip_result = result / one_pip
        pip_previous_close = previous_close / one_pip
        # LOG BASED ON PREDICTIONS
        if result > previous_close:
            direction = "Higher"
            limit = pip_result - pip_previous_close
        else:
            direction = "Lower"
            limit = pip_previous_close - pip_result
        
        if limit > trade_margin:
            took_trade = True
        else:
            took_trade = False
        
        trade_log[date] = {
            "close":actual_close,
            "prediction":result,
            "predicted_direction_from_current":direction,
            "previous_close":previous_close,
            "took_trade":took_trade
        }
        with open(f"Backtesting\\{ticker_file}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_intervals_{str(training_data_intervals)}.json","w") as f:
            json.dump(trade_log, f, indent=2,sort_keys=True)

    # CLOSE CONNECTION AT THE END
    con.close()