#!/usr/bin/env python
# coding: utf-8

# Variables
SYMBOL = "ETHUSDT"
INTERVAL = "5m"
RSI_THRESHOLD_LOW = 20
RSI_THRESHOLD_HIGH = 27
RSI_WINDOW = 14
STOCH_SMA = 3
REWARD = 1.03
RISK = 0.985
MINUTES = 120
QUANTITY = 0.45

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


# In[1]::
load_dotenv()


# In[2]:


#Loading my Bybit's API keys from the dotenv file
api_key_pw = os.getenv('api_key_bot_IP')
api_secret_pw = os.getenv('api_secret_bot_IP')
sender_pass = os.getenv('mail_key')
receiver_address = os.getenv('mail')

# In[3]:


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


# In[4]:


#This function gets Real ETH Price Data and creates a smooth dataframe that refreshes every 5 minutes
def get5minutedata():
    frame = pd.DataFrame(session_auth.query_kline(symbol=SYMBOL, interval=INTERVAL)["result"])
    frame = frame.iloc[:,: 6]
    frame.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
    frame = frame.set_index("Time")
    frame.index = pd.to_datetime(frame.index, unit="ms")
    frame = frame.astype(float)
    return frame


# In[5]:


#Function to apply some technical indicators from the ta library
def apply_technicals(df):
    df["K"] = ta.momentum.stochrsi(df.Close, window= RSI_WINDOW)
    df["D"] = df["K"].rolling(STOCH_SMA).mean()
    df["RSI"] = ta.momentum.rsi(df.Close, window = RSI_WINDOW)
    df.dropna(inplace=True)


# In[6]:


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


# In[7]:


def strategy_long(qty = QUANTITY, open_position = False):
    df= get5minutedata()
    apply_technicals(df)
    print(f'Current Time is ' + str(df.index[-1]))
    print(f'Current Close is '+str(df.Close.iloc[-1]))
    print(f"RSI: {round(df.RSI.iloc[-1], 2)}")
    print("-----------------------------------------")

    '''The following algorithm checks if the RSI is less than {RSI_THRESHOLD_LOW} ex. 20 and then it enters a while loop. 
    Inside the while loop, it continuously monitors the RSI and the close price of Ethereum. 
    Once the RSI increases to above {RSI_THRESHOLD_HIGH} ex. 30 and the close price of Ethereum makes a lower low, 
    it enters a long position in Ethereum using the session.place_active_order() function and sends an email to the user.'''

    if df.RSI.iloc[-1] < RSI_THRESHOLD_LOW:
        previous_price = round(df.Close.iloc[-1], 2)
        start_time = time.time()
        while (time.time() - start_time) < (MINUTES * 60):
            time.sleep(30) # sleep for 30 secs
            df = get5minutedata()
            apply_technicals(df)
            if df["RSI"][-1] >= RSI_THRESHOLD_HIGH and df['Close'][-1] < previous_price:
                # If the RSI increases to 30 and the price makes a lower low, enter a long position in Ethereum
                print('Enter a long position in Ethereum')
                price = round(df.Close.iloc[-1],2)
                tp = round(price * REWARD,2)
                sl = round(price * RISK,2)
                send_email(subject = f"{SYMBOL} Open Long", buy_price=price, exit_price=tp, stop=sl)

                print("-----------------------------------------")

                print(f"Buyprice: {price}")

                print("-----------------------------------------------------------------------------------------------------------------------------------------------")

                order = session.place_active_order(symbol=SYMBOL,
                                            side="Buy",
                                            order_type="Market",
                                            qty= qty,
                                            time_in_force="GoodTillCancel",
                                            reduce_only=False,
                                            close_on_trigger=False,
                                            take_profit = tp,
                                            stop_loss = sl)
                print(order)
                open_position = True
                break
            
            else:
                print("RSI has reached threshold but the price is not making a lower low, no action taken")
                print("----------------------------------------------------------------------------------")
                break

        else:
            print("Monitoring period has ended, no action taken")

    while open_position:
        time.sleep(10)
        df = get5minutedata()
        apply_technicals(df)
        current_price = round(df.Close.iloc[-1], 2)
        current_profit = round((current_price-price) * qty, 2)
        print(f"Buyprice: {price}" + '             Close: ' + str(df.Close.iloc[-1]))
        print(f'Target: ' + str(tp) + "                Stop: " + str(sl))
        print(f'RSI: {round(df.RSI.iloc[-1], 2)}')
        print(f'Current Profit : {current_profit}')
        print("-----------------------------------------------------")

        if current_price <= sl: 
            result = round((sl - price) * qty,2)
            print("Closed Position")
            send_email(subject=f"{SYMBOL} Long SL", result = result, buy_price=price, stop= sl)
            open_position = False
            exit()
        
        elif current_price >= tp:
            result= round((tp - price) * qty, 2)
            print("Closed Position")
            send_email(subject =f"{SYMBOL} Long TP", result = result, buy_price=price, exit_price= tp)
            open_position = False
            break

# In[8]:


while True: 
    strategy_long(QUANTITY)
    time.sleep(15)