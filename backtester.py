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
    training_data_intervals = 30000

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


    # CREATE DEFAULT FOLDERS AND FILES IF THEY DONT EXIST
    if not os.path.exists("Backtesting"):
        os.mkdir("Backtesting")
    if not os.path.exists(f"Backtesting\\{ticker_file}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_intervals_{str(training_data_intervals)}.json"):
        with open(f"Backtesting\\{ticker_file}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_intervals_{str(training_data_intervals)}.json","w") as f:
            json.dump({},f)
    if not os.path.exists(f"Backtesting\\{ticker_file}_{interval}_price_log.json"):
        # CONNECT TO FXCM
        con = fxcmpy.fxcmpy(access_token=access_token, server=account_type)
        print("Generated Default configs and established a connection to FXCM.")
        print("Loading full DataFrame.")
        df = load_full_df(ticker, interval)
        df.index = df.index.astype(str)
        df.rename(columns={"askclose":"close", "askhigh":"high", "asklow":"low"},inplace=True)
        df.drop(["bidopen","bidclose","bidhigh","bidlow","askopen","tickqty"],axis=1,inplace=True)
        json_string = df.to_json(orient="index")
        new_json_data = json.loads(json_string)
        with open(f"Backtesting\\{ticker_file}_{interval}_price_log.json","w")as f:
            json.dump(new_json_data,f,indent=2,sort_keys=True)
        # CLOSE CONNECTION AT THE OF NEEDING IT
        con.close()
    # lOAD THE BACKTESTING DATA IF IT EXISTS
    all_data = pd.read_json(f"Backtesting\\{ticker_file}_{interval}_price_log.json", orient="index", convert_dates=False)
    all_data.index = all_data.index.astype(str)
    print(f"Loaded initial backtesting dataframe of {len(all_data)} values.")

    

    # GET CLOSE VALUES
    x = all_data["close"].values.tolist()
    # GET DATES
    dates = all_data.index.values.tolist()

    # OPEN TRADE LOG
    with open(f"Backtesting\\{ticker_file}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_intervals_{str(training_data_intervals)}.json","r") as f:
        trade_log = json.load(f)

    total = len(all_data) - (training_data_intervals + 5)
    # START RUNNING PREDICTIONS
    for n in range(total):
        print(f"{n}/{total}")
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
            "correct_prediction":None,
            "took_trade":took_trade
        }
        with open(f"Backtesting\\{ticker_file}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_intervals_{str(training_data_intervals)}.json","w") as f:
            json.dump(trade_log, f, indent=2,sort_keys=True)

    # OPEN TRADE LOG
    with open(f"Backtesting\\{ticker_file}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_intervals_{str(training_data_intervals)}.json","r") as f:
        trade_log = json.load(f)

    # CALC ALL CORRECT PREDICTIONS
    for i in trade_log:
        if trade_log[i]["predicted_direction_from_current"] == "Higher":
            if trade_log[i]["close"] > trade_log[i]["previous_close"]:
                trade_log[i]["correct_prediction"] = True
            else:
                trade_log[i]["correct_prediction"] = False
        else:
            if trade_log[i]["close"] < trade_log[i]["previous_close"]:
                trade_log[i]["correct_prediction"] = True
            else:
                trade_log[i]["correct_prediction"] = False
    
    # RE DUMP RESULTS WITH CORRECT PREDICTIONS
    with open(f"Backtesting\\{ticker_file}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_intervals_{str(training_data_intervals)}.json","w") as f:
        json.dump(trade_log, f, indent=2,sort_keys=True)

    # RE OPEN AS READ ONLY FOR RESULT CALCULATIONS
    with open(f"Backtesting\\{ticker_file}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_intervals_{str(training_data_intervals)}.json","r") as f:
        data = json.load(f)

    # GENERATE RESULTS
    total_predictions = list()
    correct_predictions = list()
    trades_taken = list()
    correct_trades_taken = list()
    could_have_taken = list()
    could_have_taken_correct = list()
    differences = list()


    for period in data:
        if data[period]["correct_prediction"] is None:
            continue

        total_predictions.append(1)

        if data[period]["correct_prediction"]:
            correct_predictions.append(1)

        if data[period]["took_trade"]:
            trades_taken.append(1)
            if data[period]["correct_prediction"]:
                correct_trades_taken.append(1)

        if data[period]["close"] > data[period]["prediction"]:
            differences.append(data[period]["close"]-data[period]["prediction"])
        else:
            differences.append(data[period]["prediction"]-data[period]["close"])
        
        if data[period]["predicted_direction_from_current"] == "Higher":
            if (data[period]["prediction"] - data[period]["previous_close"]) > trade_margin:
                could_have_taken.append(1)
                if (data[period]["close"] - data[period]["previous_close"]) > trade_margin:
                    could_have_taken_correct.append(1)
        else:
            if (data[period]["previous_close"] - data[period]["prediction"]) > trade_margin:
                could_have_taken.append(1)
                if (data[period]["previous_close"] - data[period]["close"]) > trade_margin:
                    could_have_taken_correct.append(1)

    if len(total_predictions) > 0:
        prediction_percentage = len(correct_predictions)/len(total_predictions)*100
    else:
        prediction_percentage = 0
        
    if len(trades_taken) > 0:
        taken_percentage = len(correct_trades_taken)/len(trades_taken)*100
    else:
        taken_percentage = 0
    if len(could_have_taken):
        profit_percentage = len(could_have_taken_correct)/len(could_have_taken)*100
    else:
        profit_percentage = 0
    
    difference_average = 0
    for i in differences:
        difference_average = difference_average + i
    difference_average = difference_average/len(differences)

    print(f"Total number of correct predictions {len(correct_predictions)}/{len(total_predictions)} This is an overall accuracy of {prediction_percentage}%\nOut of this amount {len(trades_taken)} were taken and {len(correct_trades_taken)} of those were correct, this is an actual accuracy of {taken_percentage}%.\nOut of {len(total_predictions)} predictions, {len(could_have_taken)} trades could have been taken.\nOut of that amount, {len(could_have_taken_correct)} would have been profitable.\nThat is a possible profitability percentage of {profit_percentage}%\nThat is an average of only {difference_average} away from predicting on point.")
