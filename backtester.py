import json
import datetime as dt
import pandas as pd
import os
from statsmodels.tsa.arima_model import ARIMA
import warnings

if __name__ == "__main__":
    # CONFIGURABLE SETTINGS
    arima_order = (5,1,0)
    training_data_days = 98

    # DEFAULT SETTINGS
    warnings.filterwarnings('ignore', 'statsmodels.tsa.arima_model.ARMA',
                        FutureWarning)
    warnings.filterwarnings('ignore', 'statsmodels.tsa.arima_model.ARIMA',
                        FutureWarning)
    with open('APISettings.json','r') as f:
        config = json.load(f)
    API_Secret = config["API_Secret"]
    API_Key = config["API_Key"]
    interval = config["Interval"]
    ticker = config["Ticker"]
    Polo = Poloniex(API_Key,API_Secret)
    start_day = dt.datetime(2019,8,1)
    last_day = start_day + dt.timedelta(days=training_data_days)
    training_dates = list()

    # GENERATE ALL INTERVALS BETWEEN THE PERIOD
    start_day_string = dt.datetime.strftime(start_day, "%Y-%m-%d %H:%M:%S")
    last_day_string = dt.datetime.strftime(last_day, "%Y-%m-%d %H:%M:%S")
    while True:
        if start_day >= last_day:
            print(f"Loaded all {len(training_dates)} intervals between {start_day_string} and {last_day_string}")
            break
        string_datetime = dt.datetime.strftime(start_day, "%Y-%m-%d %H:%M:%S")
        training_dates.append(string_datetime)
        start_day = start_day + dt.timedelta(seconds=interval)

    if not os.path.exists("Backtesting"):
        os.mkdir("Backtesting")
    if not os.path.exists(f"Backtesting\\{ticker}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_days_{str(training_data_days)}.json"):
        with open(f"Backtesting\\{ticker}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_days_{str(training_data_days)}.json","w") as f:
            json.dump({},f)
    if not os.path.exists(f"Backtesting\\{ticker}_{interval}_price_log.json"):
        print("Loading full DataFrame.")
        df = Polo.auto_create_df(ticker,interval,full_df=True)
        df.drop(["high","low","open","volume","quoteVolume","weightedAverage"],axis=1,inplace=True)
        json_string = df.to_json(orient="index")
        new_json_data = json.loads(json_string)
        with open(f"Backtesting\\{ticker}_{interval}_price_log.json","w")as f:
            json.dump(new_json_data,f,indent=2,sort_keys=True)
    with open(f"Backtesting\\{ticker}_{interval}_price_log.json","r") as f:
        all_data = json.load(f)
    # GET FINAL DATE FROM ALL DATA TO STOP 
    final_date_string = list(all_data.keys())[-1]
    final_date = dt.datetime.strptime(final_date_string, "%Y-%m-%d %H:%M:%S")
    # LOAD BACKTESTING DATA
    backtesting_data = {}
    for key in sorted(training_dates):
        if key in all_data:
            backtesting_data[key] = all_data[key]
    print(f"Loaded initial backtesting dataframe of {len(backtesting_data)} values.")

    while True:
        # OPEN TRADE LOG
        with open(f"Backtesting\\{ticker}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_days_{str(training_data_days)}.json","r") as f:
            trade_log = json.load(f)

        # CREATE DF FROM BACKTESTING DATA DICT
        df = pd.DataFrame.from_dict(backtesting_data, orient="index")
        df.index.name = "period"
        df.index = df.index.astype(str)
        x = df["close"].values
        # GET PREVIOUS CLOSE FOR HIGHER/LOWER CHECKS
        previous_close = df.tail(2).head(1)['close'].item()
        current_interval = dt.datetime.strptime(df.tail(1).index.item(), "%Y-%m-%d %H:%M:%S")
        next_interval =  current_interval + dt.timedelta(seconds=interval)
        next_interval_string = dt.datetime.strftime(next_interval, "%Y-%m-%d %H:%M:%S")
        training_dates.append(next_interval_string)

        # TRAIN THE MODEL
        model = ARIMA(x, order=arima_order)
        model_fit = model.fit(disp=0)
        output = model_fit.forecast()
        result = output[0][0]
        # LOG PREDICTIONS BASED ON CURRENT PRICE
        if result > previous_close:
            direction = "Higher"
            difference = result - previous_close
        else:
            direction = "Lower"
            difference = previous_close - result
        
        # ALL THE TRADING LOGIC HERE BASED ON DIRECTION AND IF THERE ARE ANY OPEN TRADES OF THAT TICKER 
        if difference >= 5:
            took_trade = True
        else:
            took_trade = False
        
         # UPDATE JSON DICT WITH NEW PREDICTION DATA AND DUMP IT
        trade_log[dt.datetime.strftime(current_interval,"%Y-%m-%d %H:%M:%S")] = {"close":None,"prediction":result,"predicted_direction_from_current":direction,"previous_close":previous_close,"correct_prediction":None,"took_trade":took_trade}
        
        # ADD NEXT INTERVAL DATA TO BACKTESTING DATA
        first_key = list(backtesting_data.keys())[0]
        current_interval_string = dt.datetime.strftime(current_interval, "%Y-%m-%d %H:%M:%S")
        print(f"Backtested data using {first_key} to {current_interval_string}.")
        if next_interval_string in all_data:
            backtesting_data[next_interval_string] = all_data[next_interval_string]
        # DELETE OLDEST VAL
        del backtesting_data[first_key]

        # UPDATE CLOSE PRICES
        update_trade_log = list()
        for date in trade_log:
            if date in all_data:
                if all_data[date]["close"] != trade_log[date]["close"]:
                    trade_log[date]["close"] = all_data[date]["close"]
                    update_trade_log.append(date)
        # UPDATE TRADE LOG DATA NOW WE HAVE CLOSE
        for date in update_trade_log:
            if trade_log[date]["correct_prediction"] is not None:
                continue
            if trade_log[date]["predicted_direction_from_current"] == "Lower":
                if type(trade_log[date]["close"]) is not float:
                    continue
                elif type(trade_log[date]["previous_close"]) is not float:
                    continue
                if trade_log[date]["previous_close"] > trade_log[date]["close"]:
                    trade_log[date]["correct_prediction"] = True
                else:
                    trade_log[date]["correct_prediction"] = False
            else:
                if type(trade_log[date]["close"]) is not float:
                    continue
                elif type(trade_log[date]["previous_close"]) is not float:
                    continue
                if trade_log[date]["previous_close"] < trade_log[date]["close"]:
                    trade_log[date]["correct_prediction"] = True
                else:
                    trade_log[date]["correct_prediction"] = False
        
        with open(f"Backtesting\\{ticker}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_days_{str(training_data_days)}.json","w")as f:
            json.dump(trade_log,f,indent=2,sort_keys=True)

        if next_interval > final_date:
            print("Reached the end of backtesting, stopping now.")
            break
    
    total_predictions = list()
    correct_predictions = list()
    trades_taken = list()
    correct_trades_taken = list()
    could_have_taken = list()
    could_have_taken_correct = list()
    with open(f"Backtesting\\{ticker}_{interval}_trade_log_arima_order_{str(arima_order)}_training_data_days_{str(training_data_days)}.json","r") as f:
        data = json.load(f)

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
        
        if data[period]["predicted_direction_from_current"] == "Higher":
            if (data[period]["prediction"] - data[period]["previous_close"]) > 5:
                could_have_taken.append(1)
                if (data[period]["close"] - data[period]["previous_close"]) > 5:
                    could_have_taken_correct.append(1)
        else:
            if (data[period]["previous_close"] - data[period]["prediction"]) > 5:
                could_have_taken.append(1)
                if (data[period]["previous_close"] - data[period]["close"]) > 5:
                    could_have_taken_correct.append(1)

    if len(total_predictions) > 0:
        prediction_percentage = len(correct_predictions)/len(total_predictions)*100
    else:
        prediction_percentage = 0
        
    if len(trades_taken) > 0:
        taken_percentage = len(correct_trades_taken)/len(trades_taken)*100
    else:
        taken_percentage = 0
    profit_percentage = len(could_have_taken_correct)/len(could_have_taken)*100
    print(f"Total number of correct predictions {len(correct_predictions)}/{len(total_predictions)} This is an overall accuracy of {prediction_percentage}%\nOut of this amount {len(trades_taken)} were taken and {len(correct_trades_taken)} of those were correct, this is an actual accuracy of {taken_percentage}%.\nOut of {len(total_predictions)} predictions, {len(could_have_taken)} trades could have been taken.\nOut of that amount, {len(could_have_taken_correct)} would have been profitable.\nThat is a possible profitability percentage of {profit_percentage}%")