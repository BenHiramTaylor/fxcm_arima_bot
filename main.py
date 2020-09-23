import datetime as dt
import fxcmpy
import json
import os
import pandas as pd
import time

def get_one_percent():
    global con
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

def reload_configs():
    # RELOAD ALL GLOBAL CONFIGS TO ALLOW FOR SWAPPING TRADES WITHOUT CLOSING BOT
    global interval, ticker, auto_trade, account_type, account_id
    if not os.path.exists("APISettings.json"):
        raise Exception("APISettings.json not present, cannot read configs, please create APISettings.json")
    with open("APISettings.json", "r") as f:
        config = json.load(f)
    interval = config["interval"]
    ticker = config["ticker"]
    auto_trade = config["auto_trade"]
    account_type = config["account_type"]
    account_id = config["account_id"]

if __name__ == "__main__":
    # CHECK IF APISettings.json IS PRESENT AND LOAD DEFAULT CONFIGS
    if not os.path.exists("APISettings.json"):
        raise Exception("APISettings.json not present, cannot read configs, please create APISettings.json")
    if not os.path.exists("JSON"):
        os.mkdir("JSON")
    with open("APISettings.json", "r") as f:
        config = json.load(f)
    # CREATE DEFAULT VARS AND RELOAD USING reload_configs
    access_token = config["access_token"]
    account_id = config["account_id"]
    account_type = config["account_type"]
    interval = None
    ticker = None
    auto_trade = None
    next_interval = None
    con = fxcmpy.fxcmpy(access_token=access_token, server=account_type, log_file=f"Bot_Logs.txt", log_level="warn")
    print("Generated Default configs and established a connection to FXCM.")

    while True:
        # LOAD ALL CONFIGS EACH RUN
        reload_configs()

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
            elif time_since_run >= interval:
                print(f"It has been {time_since_run} seconds since last run. running now..")
            else:
                last_run_dt = dt.datetime.fromtimestamp(LastRun)
                next_interval = last_run_dt + dt.timedelta(seconds=interval)
                continue
        else:
            next_interval = next_interval + dt.timedelta(seconds=10)
            next_interval_sleep = next_interval.timestamp()-dt.datetime.now().timestamp()
            if next_interval_sleep > 0:
                next_interval_string = dt.datetime.strftime(next_interval,"%Y-%m-%d %H:%M:%S")
                print(f"We have the next interval, sleeping until then. See you in {next_interval_sleep} seconds at {next_interval_string}")
                time.sleep(next_interval_sleep)
        
        # REFRESH ALL OPEN POSITIONS
        open_positions = con.get_open_positions(kind="list")
        # TODO ADD LOGIC HERE TO KILL OFF OLD TRADES BASED ON A TRADE PLAN


        # CLOSE THE FXCM THREADED CONNECTION
        con.close()
        break