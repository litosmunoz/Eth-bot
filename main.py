#!/usr/bin/env python
# coding: utf-8

# In[1]:

# Variables
SYMBOL = "ETHUSDT"
INTERVAL = "5m"
RSI_ENTER = 78
RSI_EXIT = 24
RSI_WINDOW = 14
STOCH_SMA = 3
REWARD = 0.93 #7%
RISK = 1.03   #3%

import pandas as pd
import numpy as np
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os
import time
import ta 
import warnings
warnings.simplefilter("ignore")


# In[2]:


load_dotenv()


# In[3]:


#Loading my Bybit's API keys and mail info from the dotenv file
api_key_pw = os.getenv('api_key_bot_IP')
api_secret_pw = os.getenv('api_secret_bot_IP')
sender_pass = os.getenv('mail_key')
receiver_address = os.getenv('mail')


# In[4]:


#Establishing Connection with the API (SPOT)
from pybit import spot
session_auth = spot.HTTP(
    endpoint='https://api.bybit.com',
    api_key = api_key_pw,
    api_secret= api_secret_pw
)

#Establishing Connection with the API (FUTURES)
from pybit import usdt_perpetual
session = usdt_perpetual.HTTP(
    endpoint='https://api.bybit.com',
    api_key = api_key_pw,
    api_secret= api_secret_pw
)


# In[5]:


#This function gets Real ETH Price Data and creates a smooth dataframe that refreshes every 5 minutes
def get5minutedata():
    frame = pd.DataFrame(session_auth.query_kline(symbol=SYMBOL, interval=INTERVAL)["result"])
    frame = frame.iloc[:,: 6]
    frame.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
    frame = frame.set_index("Time")
    frame.index = pd.to_datetime(frame.index, unit="ms")
    frame = frame.astype(float)
    return frame


# In[6]:


#Function to apply some technical indicators from the ta library
def apply_technicals(df):
    df["K"] = ta.momentum.stochrsi(df.Close, window= RSI_WINDOW)
    #df["D"] = df["K"].rolling(3).mean()
    df["RSI"] = ta.momentum.rsi(df.Close, window = RSI_WINDOW)
    df.dropna(inplace=True)



# In[7]:


class Signals:
    def __init__(self, df, lags):
        self.df = df
        self.lags = lags
    
    #Checking if we have a trigger in the last n time steps
    def get_trigger(self):
        df_2 = pd.DataFrame()
        for i in range(self.lags + 1):
            mask = (self.df["RSI"].shift(i) > RSI_ENTER)
            df_2 = df_2.append(mask, ignore_index = True)
        return df_2.sum(axis= 0)
    
    # Is the trigger fulfilled and are all buying conditions fulfilled?
    def decide(self):
         self.df["trigger"] = np.where(self.get_trigger(), 1, 0)
         self.df["Sell"]= np.where((self.df.trigger), 1, 0)



# In[8]:


#The sender mail address and password
sender_address = 'pythontradingbot11@gmail.com'

#Function to automate mails
def send_email(subject, result = None, buy_price = None, exit_price = None, stop = None):
    content = ""
    if result is not None:
      content += f"Result: {result}\n"
    if buy_price is not None:
      content += f"Buy Price: {buy_price}\n"
    if exit_price is not None:
      content += f"TP Price: {exit_price}\n"
    if stop is not None:
      content += f"SL Price: {stop}\n"

    message = MIMEMultipart()
    message['From'] = sender_address
    message['To'] = receiver_address
    message['Subject'] = subject 
    message.attach(MIMEText(content, 'plain'))
    
    #Create SMTP session for sending the mail
    session_mail = smtplib.SMTP('smtp.gmail.com', 587)  # use gmail with port
    session_mail.starttls()  # enable security
    session_mail.login(sender_address, sender_pass)
    text = message.as_string()
    session_mail.sendmail(sender_address, receiver_address, text)
    session_mail.quit()


# In[10]:


def strategy_short(qty, open_position = False):
    df= get5minutedata()
    apply_technicals(df)
    inst = Signals(df, 1)
    inst.decide()
    print(f'Current Time is ' + str(df.index[-1]))
    print(f'Current Close is '+str(df.Close.iloc[-1]))
    print(f"RSI: {round(df.RSI.iloc[-1], 2)}")
    print("-----------------------------------------")

    if df.Sell.iloc[-1]:
        buyprice = round(df.Close.iloc[-1],2)
        tp = round(buyprice * REWARD,2)
        sl = round(buyprice * RISK,2)
        send_email(subject= "ETH Open Short", buy_price=buyprice, exit_price=tp, stop=sl)
        
        print("-----------------------------------------")

        print(f"Buyprice: {buyprice}")

        print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")

        order = session.place_active_order(symbol=SYMBOL,
                                            side="Sell",
                                            order_type="Market",
                                            qty= qty,
                                            time_in_force="GoodTillCancel",
                                            reduce_only=False,
                                            close_on_trigger=False,
                                            take_profit = tp,
                                            stop_loss = sl)
        print(order)

        eth_order_id = str(order['result']['order_id'])
        print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        print(f"Order id: {eth_order_id}") 
        print("---------------------------------------------------")

        open_position = True

    while open_position:
        time.sleep(10)                          
        df = get5minutedata()
        apply_technicals(df)
        print(f"Buyprice: {buyprice}" + '             Close: ' + str(df.Close.iloc[-1]))
        print(f'Target: ' + str(tp) + "               Stop: " + str(sl))
        print(f'RSI Target: {RSI_EXIT}                RSI: {round(df.RSI.iloc[-1], 2)}')
        print("---------------------------------------------------")

        if df.Close[-1] >= sl:
            result = round((buyprice - sl)*qty,2)
            print("Closed Position")
            open_position = False
            send_email(sybject= "ETH Short SL", result=result, buy_price=buyprice, exit_price=sl)
            exit()

        elif df.Close[-1] <= tp: 
            result = round((buyprice - tp)*qty,2)
            print("Closed Position")
            open_position = False
            send_email(sybject= "ETH Short TP", result=result, buy_price=buyprice, exit_price=tp)
            break

        elif df.RSI[-1] < RSI_EXIT:
            
            try: 
                print(session.place_active_order(symbol="ETHUSDT",
                                                side="Buy",
                                                order_type="Market",
                                                qty= qty,
                                                time_in_force="GoodTillCancel",
                                                reduce_only=True,
                                                close_on_trigger=False))  

                print("---------------------------------------------------")
                rsi_exit_price = round(df.Close.iloc[-1],2)
                result= round((buyprice -rsi_exit_price)*qty,2)  
                print("Closed position")
                open_position = False
                send_email(subject= f"ETH Short Closed - RSI < {RSI_EXIT}", result=result, buy_price=buyprice, exit_price=rsi_exit_price)
                break

            except: 
                print("Position already closed")
                send_email(subject="Position already Closed")             
                break


# In[11]:


while True: 
    strategy_short(0.6)
    time.sleep(15)






