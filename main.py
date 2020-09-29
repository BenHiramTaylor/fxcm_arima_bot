import datetime as dt
import fxcmpy
import json
import os
import pandas as pd
import time
from statsmodels.tsa.arima_model import ARIMA
import warnings

def KillOldTrades():
    new_open_positions = list()
    # REFRESH ALL OPEN POSITIONS
    open_positions = con.get_open_positions(kind="list")
    killed_positions = False
    # KILL OFF OLD TRADES IF STILL OPEN
    # if next_interval:
    #     set_periods_ago = next_interval - dt.timedelta(seconds=interval_seconds*max_trade_open_time)
    #     if len(open_positions):
    #         for t in open_positions:
    #             tradeTS = dt.datetime.fromtimestamp(t["time"])
    #             if tradeTS < set_periods_ago:
    #                 print(f"Killing trade with ID: {t['tradeId']}, it has been open for more than the specified intervals.")
    #                 con.close_trade(t["tradeId"])
    #                 killed_positions = True
    
    # REFRESH POSITIONS IF KILLED TRADES
    if killed_positions:
        open_positions = con.get_open_positions(kind="list")
    
    if len(open_positions):
        for obj in open_positions:
            if obj["currency"] not in new_open_positions:
                new_open_positions.append(obj["currency"])
    return new_open_positions

def calculate_lot_size(price_per_pip):
    # CALCULATE A 2:1 RR
    accounts= con.get_accounts(kind="list")
    balance = None
    for i in accounts:
        if i["accountId"] == account_id:
            balance = i["balance"]
    if not balance:
        print(f"Account with ID {account_id} not found in con.get_accounts.")
        con.close()
        exit(1)
    one_percent = balance / 100
    one_lot_value = 100000*price_per_pip
    lots = one_percent / one_lot_value
    return int(lots)

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
     # TURN OFF ARIMA MODEL WARNINGS
    warnings.filterwarnings('ignore', 'statsmodels.tsa.arima_model.ARMA',FutureWarning)
    warnings.filterwarnings('ignore', 'statsmodels.tsa.arima_model.ARIMA',FutureWarning)

    # CHECK IF APISettings.json IS PRESENT AND LOAD DEFAULT CONFIGS
    if not os.path.exists("APISettings.json"):
        raise Exception("APISettings.json not present, cannot read configs, please create APISettings.json")
    if not os.path.exists("JSON"):
        os.mkdir("JSON")
    with open("APISettings.json", "r") as f:
        config = json.load(f)

    # CREATE DEFAULT VARS
    period_to_seconds = {"m5":300,"m15":900,"H1":3600}
    one_pip = 0.0001

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
    firstRun = True

    # CONNECT TO FXCM
    con = fxcmpy.fxcmpy(access_token=access_token, server=account_type, log_file=f"Bot_Logs.txt", log_level="error")
    print("Generated Default configs and established a connection to FXCM.")
    # SET THE DEFAULT ACCOUNT USING THE ACCOUNT ID PROVIDED
    con.set_default_account(account_id)

    # BEGIN TRADING BOT LOOP
    while True:
        # REFRESH AUTO_TRADE INCASE CHANGED
        with open("APISettings.json", "r") as f:
            config = json.load(f)
        auto_trade = config["auto_trade"]
        trade_margin = config["trade_margin"]

        # CHECK IF SUBSCRIBED TO TICKER STREAM AND SUBSCRIBE IF NOT
        if not con.is_subscribed(ticker):
            con.subscribe_market_data(ticker)

        # LOAD SPREAD FOR TICKER HERE GET CURRENT PRICE AND CALC PRICE PER PIP
        spread_df = con.get_offers()
        spread_df.set_index("currency", inplace=True)
        spread = spread_df.loc[ticker,:]["spread"].item()
        current_buy_price = spread_df.loc[ticker,:]["buy"].item()
        current_sell_price = spread_df.loc[ticker,:]["sell"].item()
        price_per_pip = spread_df.loc[ticker,:]["pipCost"].item()

        # LOAD LAST RUN TIMES, ADD TICKER DEFAULT TO 0
        if not os.path.exists(f"JSON\\LastRunTimes_{interval}.json"):
            with open(f"JSON\\LastRunTimes_{interval}.json","w") as f:
                json.dump({},f)
        with open(f"JSON\\LastRunTimes_{interval}.json","r") as f:
            LastRunTimes = json.load(f)
        if ticker not in LastRunTimes:
            LastRunTimes[ticker] = 0
        LastRun = LastRunTimes[ticker]

        if not next_interval:
            time_since_run = dt.datetime.now().timestamp() - LastRun
            if LastRun == 0:
                print("Bot never run before, running for first time...")
            elif time_since_run >= interval_seconds:
                print(f"It has been {time_since_run} seconds since last run. running now..")
            else:
                last_run_dt = dt.datetime.fromtimestamp(LastRun)
                next_interval = last_run_dt + dt.timedelta(seconds=interval_seconds)
                continue
        else:
            next_interval = next_interval + dt.timedelta(seconds=30)
            next_interval_sleep = next_interval.timestamp()-dt.datetime.now(tz=dt.timezone.utc).timestamp()
            if next_interval_sleep > 0:
                next_interval_string = dt.datetime.strftime(next_interval,"%Y-%m-%d %H:%M:%S%z")
                print(f"We have the next interval, sleeping until then. See you in {next_interval_sleep} seconds at {next_interval_string}")
                time.sleep(next_interval_sleep)
        
        # SLEEPING ON HOLS AND MARKET CLOSE TIME
        today = dt.datetime.now(tz=dt.timezone.utc)
        if today.month == 12:
            if today.day == 25:
                print("It is Christmas Day! No trading today! Merry Christmas!")
                time.sleep(86400)
                next_interval = None
                continue
        elif today.month == 1:
            if today.day == 1:
                print("It is the new year today! Happy new year!!")
                time.sleep(86400)
                next_interval = None
                continue
        elif today.today().weekday() == 5:
            if today.hour == 20:
                print("Markets closing in one hour for the weekend!, closing all trades, see you in 187200 seconds!")
                con.close_all()
                time.sleep(187200)
                next_interval = None
                continue
        
        # REFRESH ALL OPEN POSITIONS AND KILL OLD ONES
        open_positions = KillOldTrades()

        # CREATE DF AND DUMP TO JSON
        if not os.path.exists(f"JSON\\{ticker_file}_{interval}_price_log.json"):
            print("Loading full DataFrame.")
            df = load_full_df(ticker, interval)
            df.index = df.index.astype(str)
            df.rename(columns={"askclose":"close", "askhigh":"high", "asklow":"low"},inplace=True)
            df.drop(["bidopen","bidclose","bidhigh","bidlow","askopen","tickqty"],axis=1,inplace=True)
            json_string = df.to_json(orient="index")
            new_json_data = json.loads(json_string)
            with open(f"JSON\\{ticker_file}_{interval}_price_log.json","w")as f:
                json.dump(new_json_data,f,indent=2,sort_keys=True)
            # GET PREVIOUS CLOSE FOR HIGHER/LOWER CHECKS
            previous_close = df.tail(2).head(1)['close'].item()
            current_interval = dt.datetime.strptime(df.tail(1).index.item(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
            next_interval =  current_interval + dt.timedelta(seconds=interval_seconds)
        else:
            print("Loading existing DataFrame and updating with new records.")
            df = pd.read_json(f"JSON\\{ticker_file}_{interval}_price_log.json", orient="index", convert_dates=False)
            df.index.name = "date"

        while True:
            # GET UPDATED DF
            new_df = con.get_candles(instrument=ticker,period=interval,number=10000)
            new_df.index = new_df.index.astype(str)
            new_df.rename(columns={"askclose":"close", "askhigh":"high", "asklow":"low"},inplace=True)
            new_df.drop(["bidopen","bidclose","bidhigh","bidlow","askopen","tickqty"],axis=1,inplace=True)
            # GET PREVIOUS CLOSE FOR HIGHER/LOWER CHECKS
            previous_close = new_df.tail(2).head(1)['close'].item()
            current_interval = dt.datetime.strptime(new_df.tail(1).index.item(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
            next_interval =  current_interval + dt.timedelta(seconds=interval_seconds)
            if next_interval > dt.datetime.now(tz=dt.timezone.utc):
                break
            else:
                print_current_interval = dt.datetime.strftime(current_interval, "%Y-%m-%d %H:%M:%S")
                print(f"Current interval received was {print_current_interval}, which should be wrong, sleeping for 5 seconds and reloading DataFrame")
                time.sleep(5)
        
        df = df.append(new_df)
        df = df.reset_index().drop_duplicates(subset='date', keep='first').set_index('date')
        df.index = df.index.astype(str)
        json_string = df.to_json(orient="index")
        new_json_data = json.loads(json_string)
        with open(f"JSON\\{ticker_file}_{interval}_price_log.json","w")as f:
            json.dump(new_json_data,f,indent=2,sort_keys=True)

        # LOG TIMESTAMP OF LAST INTERVAL TO FILE
        LastRunTimes[ticker] = current_interval.timestamp()
        with open(f"JSON\\LastRunTimes_{interval}.json","w") as f:
            json.dump(LastRunTimes,f)

        with open(f"JSON\\{ticker_file}_{interval}_price_log.json","r") as f:
            json_file = json.load(f)

        # OPEN TRADE LOG
        if not os.path.exists(f"JSON\\{ticker_file}_{interval}_trade_log.json"):
            with open(f"JSON\\{ticker_file}_{interval}_trade_log.json","w") as f:
                json.dump({},f)
        with open(f"JSON\\{ticker_file}_{interval}_trade_log.json","r") as f:
            trade_log = json.load(f)        
        
        # UPDATE ALL LOG RECORDS WITH THE ACTUAL CLOSE, IF MISSING, CHECK IF PAST PREDICTIONS ARE CORRECT
        update_count = 0
        for date in trade_log:
            if date in new_json_data:
                if new_json_data[date]["close"] != trade_log[date]["close"]:
                    update_count += 1
                    trade_log[date]["close"] = new_json_data[date]["close"]

        for date in trade_log:
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


        if update_count > 0:
            print(f"Updated JSON Trade Log with {update_count} new records.")

        # TRAIN THE DATA TO GET PREDICTIONS
        x = new_df["close"].values

        model = ARIMA(x, order=(5,1,0))
        model_fit = model.fit(disp=0)
        output = model_fit.forecast()
        result = output[0][0]

        # CALCULATE VALUE IN PIPS
        pip_result = result / one_pip
        pip_previous_close = previous_close / one_pip

        # LOG PREDICTIONS BASED ON CURRENT PRICE
        if result > previous_close:
            direction = "Higher"
            isbuy = True
            limit = pip_result - pip_previous_close
        else:
            direction = "Lower"
            isbuy = False
            limit = pip_previous_close - pip_result
        
        # PRINT THE RESULTS FROM THE PREDICTION
        print(f"Predictions have predicted the price being {direction} than the previous close of: {previous_close} at the next interval of: {next_interval}.\nPrice predicted: {result}, pip difference is {limit}.")

        # SKIP TRADING ON FIRST RUN OF LOOP
        if firstRun:
            print("First run of loop, skipping trade.")
            firstRun = False
            continue
        # ALL THE TRADING LOGIC HERE BASED ON DIRECTION AND IF THERE ARE ANY OPEN TRADES OF THAT TICKER
        # ONLY TRADES IF THE DIFFERENCE MEETS THE SPECIFIED MARGIN TO TRADE + THE SPREAD
        if auto_trade:
            if limit >= spread:
                # TAKE SPREAD AWAY TO GET VALUE OF PROFIT MARGIN IN PIPS
                margin = limit - spread
                # CHECK IF THAT MARGIN IS ABOVE THE SPECIFIED TRADE MARGIN
                if margin >= trade_margin:
                    if ticker in open_positions:
                        print(f"Not initiating trade, position already open for ticker {ticker}.")
                        took_trade = False
                    else:
                        # TRADE HERE WITH SPECIFIED SETTINGS 2:1 RR AND A STOP TRAILING IN 10THS
                        stop_pips = limit/2
                        lot_size = calculate_lot_size(price_per_pip)
                        con.open_trade(
                            symbol=ticker,
                            isbuy=isbuy,
                            order_type="AtMarket",
                            is_in_pips=True,
                            trailing_step=stop_pips/10,
                            limit=limit,
                            stop=stop_pips,
                            amount=lot_size
                        )
                        took_trade = True
                else:
                    print(f"Margin is too low, no profit after removing spread, spread is {spread}, pip difference is {limit}, which makes the margin {margin}, which is lower than the specified {trade_margin}.")
                    took_trade = False
            else:
                took_trade = False
                print(f"Not initiating trade, predicted price difference was less than 5.")
        else:
            took_trade = False
            print("Not Trading, AutoTrade is set to False, to change this, please set AutoTrade to true in APISettings.json")
        
        # UPDATE JSON DICT WITH NEW PREDICTION DATA AND DUMP IT
        trade_log[dt.datetime.strftime(current_interval,"%Y-%m-%d %H:%M:%S")] = {"close":None,"prediction":result,"predicted_direction_from_current":direction,"previous_close":previous_close,"correct_prediction":None,"took_trade":took_trade}

        with open(f"JSON\\{ticker_file}_{interval}_trade_log.json","w")as f:
            json.dump(trade_log,f,indent=2,sort_keys=True)
    