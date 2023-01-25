#!/usr/bin/env python
# coding: utf-8

# Variables
SYMBOL = "ETHUSDT"
INTERVAL = "5m"
RSI_THRESHOLD_LOW = 22
RSI_THRESHOLD_HIGH = 32
RSI_WINDOW = 14
STOCH_SMA = 3
REWARD = 1.03
RISK = 0.985
LIMIT_ORDER = 0.99
MINUTES_DIVERGENCE = 120
MINUTES_LIMIT_ORDER = 360
QUANTITY = 0.6

import logging
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


# Set up logging
logging.basicConfig(filename='strategy.log', level=logging.INFO,
                    format='%(asctime)s %(message)s')

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
f'''It starts by getting the 5-minute data for Ethereum and applying certain technical indicators to it.
It then checks if the value of the 'Buy' column in the last row of the dataframe is True.
If it is True, it enters a while loop where it continuously monitors the RSI and close price of Ethereum.
If the RSI increases to above a certain threshold and the close price of Ethereum makes a lower low, it creates a limit order to enter a long position in Ethereum and sends an email to the user.
If {MINUTES_DIVERGENCE} minutes pass and the condition has not been met, the program restarts.
If the condition is met, the code monitors the status of the order and cancels the order if it has not been filled within {MINUTES_LIMIT_ORDER} minutes.'''

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
    it creates a limit order to enters a long position in Ethereum using the session.place_active_order() function and sends an email to the user.'''

    if round(df.RSI.iloc[-1], 2) < RSI_THRESHOLD_LOW:
        previous_price = round(df.Close.iloc[-1], 2)
        start_time = int(time.time())
        while (int(time.time()) - start_time) < (MINUTES_DIVERGENCE * 60):
            df = get5minutedata()
            apply_technicals(df)
            time_runner = (MINUTES_DIVERGENCE * 60) - ((int(time.time()) - start_time))
            remaining_minutes = int(time_runner / 60)
            print(f'Current Close is '+str(df.Close.iloc[-1]))
            print(f"RSI: {round(df.RSI.iloc[-1], 2)}")
            print(f"Searching for RSI > {RSI_THRESHOLD_HIGH} and a Lower Low than {previous_price}")
            print("Remaining minutes: ", remaining_minutes)
            print("-------------------------------------------------------------------------------")
            time.sleep(60) # sleep for 60 secs

            if round(df["RSI"].iloc[-1], 2) >= RSI_THRESHOLD_HIGH and round(df['Close'].iloc[-1],2) < previous_price:
                # If the RSI increases to 30 and the price makes a lower low, enter a long position in Ethereum
                print('Consider entering a long position in Ethereum')
                price = round(df.Close.iloc[-1],2)
                buyprice_limit = round(price * LIMIT_ORDER,2)
                tp = round(buyprice_limit * REWARD,2)
                sl = round(buyprice_limit * RISK,2)
                send_email(subject = f"{SYMBOL} Open Long Limit Order", buy_price=buyprice_limit, exit_price=tp, stop=sl)

                print("-----------------------------------------")

                print(f"Limit Buyprice: {buyprice_limit}")

                print("-----------------------------------------------------------------------------------------------------------------------------------------------")

                order = session.place_active_order(symbol=SYMBOL,
                                            side="Buy",
                                            order_type="Limit",
                                            qty= qty,
                                            price = buyprice_limit,
                                            time_in_force="GoodTillCancel",
                                            reduce_only=False,
                                            close_on_trigger=False,
                                            take_profit = tp,
                                            stop_loss = sl)
                print(order)

                break

        else:
            print(f"{MINUTES_DIVERGENCE} minutes have passed. Restarting program.")
            return strategy_long()


        # Set the expiration time for the order (200 mins from now)
        expiration_time = int(time.time()) + (MINUTES_LIMIT_ORDER*60)
        
        # Wait until the expiration time
        while int(time.time()) < expiration_time:
            # Sleep for 10 seconds before checking the order status again
            time.sleep(10)
            # Update time_runner
            time_runner = int((expiration_time - int(time.time()))/ 60)
            # Check the status of the order
            order_info = session.get_active_order(symbol= SYMBOL)
            order_status = str(order_info['result']["data"][0]['order_status'])
            print(f'Order Status: {order_status}')
            print("Remaining minutes: ", time_runner)
            print("---------------------------------")

            # If the order has been filled or cancelled, exit the loop
            if order_status == "Filled":
                open_position = True
                send_email(subject=f"{SYMBOL} Limit Order Filled")
                break
            elif order_status in ["Cancelled"]:
                open_position = False 
                send_email(subject=f"{SYMBOL} Order Cancelled Manually")
                break
        
        else:
            order_info = session.get_active_order(symbol= SYMBOL)
            order_status = str(order_info['result']["data"][0]['order_status'])
            print(order_status)
            print("----------------------------------------------------------------------")
            
            if order_status not in ["Filled"]: 
                try:
                    cancel_order = session.cancel_all_active_orders(symbol= SYMBOL)
                    print(cancel_order)
                    send_email(subject= f"{SYMBOL} Limit Order has not been filled before the expiration time. Cancelling order...")
                    open_position= False
                    
                except: 
                    print("No orders need to be cancelled")
        

    while open_position:
        time.sleep(15)
        df = get5minutedata()
        apply_technicals(df)
        current_price = round(df.Close.iloc[-1], 2)
        current_profit = round((current_price-buyprice_limit) * qty, 2)
        print(f"Buyprice: {buyprice_limit}" + '             Close: ' + str(df.Close.iloc[-1]))
        print(f'Target: ' + str(tp) + "                Stop: " + str(sl))
        print(f'RSI: {round(df.RSI.iloc[-1], 2)}')
        print(f'Current Profit : {current_profit}')
        print("-----------------------------------------------------")

        if current_price <= sl: 
            result = round((sl - price) * qty,2)
            print("Closed Position")
            send_email(subject=f"{SYMBOL} Long SL", result = result, buy_price=buyprice_limit, stop= sl)
            open_position = False
            exit()
        
        elif current_price >= tp:
            result= round((tp - price) * qty, 2)
            print("Closed Position")
            send_email(subject =f"{SYMBOL} Long TP", result = result, buy_price=buyprice_limit, exit_price= tp)
            open_position = False
            break



# In[8]:


while True: 
    strategy_long(QUANTITY)
    time.sleep(15)