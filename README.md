# fxcm_arima_bot
***I AM NOT RESPONSIBLE FOR ANY MONETARY LOSSES USING THIS BOT, THIS IS A CODING SIDE PROJECT AND NOTHING MORE, BY USING THIS BOT, YOU ARE ACCEPTING RESPONSIBILITY FOR ANY LOSSES YOU MAY INCUR.***

**This bot is designed to run _indefinitely_ unless one of the following things occurs:**
- You input an invalid Ticker when asked.
- You input an invalid Interval to trade.
- You kill the script or container manually. **(Be Warned, This will not close open trades.)**

**Any invalid inputs/calls will error while returning a list of valid options.**

Once this repository has been cloned, there is some setup required before it can be used.

1. Rename APISettingsTEMPLATE.json to APISettings.json
2. Fill in the values of that JSON with your personal settings.
   1. ticker: The ticker code.
   2. interval: The Interval you wish to trade in seconds.
   3. auto_trade: true will allow the bot to place trades if the criteria are met, false will run the bot without trading (good for testing predictions and backtesting).
   4. access_token: Your FXCM API Key.
   5. account_type: demo or live.
   6. account_id: The ID of the FXCM account you wish to trade.
   7. max_trade_open_time: The max number of intervals a trade is allowed to be open for before it is force killed.
3. There are two ways to run this bot: 
   1. Using the locally installed Python.
      - `pip install -r requirements.txt`
      - `python3 main.py`
   2. Or using the dockerfile.
      - To Build the docker image, `docker build -t fxcm-bot .`
      - Then to run the image, `docker run -it --rm fxcm-bot`
  
**This Bot does not support running multiple configs in one script.**

**If you wish to trade multiple Ticker/Interval combinations, Create a seperate copy of this repository with the desired settings.**
> Copyright of Ben Hiram Taylor