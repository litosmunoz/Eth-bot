#!/usr/bin/env python
# coding: utf-8

# In[1]:

# Variables
rsi_enter = 32
K_enter = 0.15

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


#Loading my Bybit's API keys from the dotenv file
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


#This function gets Real SOL Price Data and creates a smooth dataframe that refreshes every 5 minutes
def get5minutedata():
    frame = pd.DataFrame(session_auth.query_kline(symbol="SOLUSDT", interval="5m")["result"])
    frame = frame.iloc[:,: 6]
    frame.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
    frame = frame.set_index("Time")
    frame.index = pd.to_datetime(frame.index, unit="ms")
    frame = frame.astype(float)
    return frame


# In[6]:


#Function to apply some technical indicators from the ta library
def apply_technicals(df):
    df["K"] = ta.momentum.stochrsi(df.Close, window= 14)
    df["D"] = df["K"].rolling(3).mean()
    df["RSI"] = ta.momentum.rsi(df.Close, window = 14)
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
            mask = (self.df["RSI"].shift(i) < rsi_enter)
            df_2 = df_2.append(mask, ignore_index = True)
        return df_2.sum(axis= 0)
    
    # Is the trigger fulfilled and are all buying conditions fulfilled?
    def decide(self):
         self.df["trigger"] = np.where(self.get_trigger(), 1, 0)
         self.df["Buy"]= np.where((self.df.trigger) & 
                                    (self.df["K"] > self.df["D"]) & 
                                    (self.df["K"]) < K_enter, 1, 0)



# In[8]:


#The sender mail address
sender_address = 'pythontradingbot11@gmail.com'

#Function to automate mails
def send_email(mail_content):
    message = MIMEMultipart()
    message.attach(MIMEText(mail_content, 'plain'))
    # Create SMTP session for sending the mail
    session_mail = smtplib.SMTP('smtp.gmail.com', 587)  # use gmail with port
    session_mail.starttls()  # enable security
    session_mail.login(sender_address, sender_pass)
    text = message.as_string()
    session_mail.sendmail(sender_address, receiver_address, text)
    session_mail.quit()


# In[9]:


def strategy_long(qty, open_position = False):
    df= get5minutedata()
    apply_technicals(df)
    inst = Signals(df, 1)
    inst.decide()
    print(f'Current Time is ' + str(df.index[-1]))
    print(f'Current Close is '+ str(df.Close.iloc[-1]))
    print(f"RSI: {round(df.RSI.iloc[-1], 2)}  K: {round(df.K.iloc[-1], 2)}  D: {round(df.D.iloc[-1], 2)}")
    print("-----------------------------------------")

    if df.Buy.iloc[-1]:
        send_email("SOL Open Long Limit Order")
        price = round(df.Close.iloc[-1],2)
        buyprice_limit = round(price * 0.995,2)
        tp = round(price * 1.04,2)
        sl = round(price * 0.983,2)
        
        print("-----------------------------------------")

        print(f"Limit Buyprice: {buyprice_limit}")

        print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")

        order = session.place_active_order(symbol="SOLUSDT",
                                            side="Buy",
                                            order_type="Limit",
                                            price = buyprice_limit,
                                            qty= qty,
                                            time_in_force="GoodTillCancel",
                                            reduce_only=False,
                                            close_on_trigger=False,
                                            take_profit = tp,
                                            stop_loss = sl)
        print(order)

        sol_order_id = str(order['result']['order_id'])
        print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        print(f"Order id: {sol_order_id}")
        print("---------------------------------------------------")


        '''The next code sets the expiration time to be 9000 seconds (150 minutes) in the future by using expiration_time = int(time.time()) + 9000.
        It then enters a while loop that continues to execute as long as the current time is less than the expiration time. 
        In each iteration of the while loop, it check the status of the order by getting the order information using session.get_active_order(symbol= "SOLUSDT") and gets the order status by checking the order_info['result']["data"][0]['order_status']. 
        Then it checks the order status, if the status is "Filled" or "Cancelled" it will break the loop.
        It also has a sleep for 10 seconds before checking the order status again, this is to prevent the loop from continuously checking the order status which could cause problems with the API or slow down the program.

        After the while loop it checks if the current time is greater than the expiration time, if it is then it will check the order status again, if the order status is not "Filled" it will cancel the order by calling session.cancel_all_active_orders(symbol= "SOLUSDT") and prints the response of the cancel_order API.
        This code should work as expected and check the order status for 150 minutes, and if the order is not filled or cancelled within 150 minutes it will automatically cancel the order.'''

        # Set the expiration time for the order (150 mins from now)
        expiration_time = int(time.time()) + (150*60)

        # Wait until the expiration time
        while int(time.time()) < expiration_time:
            # Sleep for 10 seconds before checking the order status again
            time.sleep(10)

            # Check the status of the order
            order_info = session.get_active_order(symbol= "SOLUSDT")
            order_status = str(order_info['result']["data"][0]['order_status'])
            print(order_status)
            print("------------------------")

            # If the order has been filled or cancelled, exit the loop
            if order_status in ["Filled"]:
                open_position = True
                break
            elif order_status in ["Cancelled"]:
                open_position = False 
                break
            
        
        if int(time.time()) > expiration_time:
            order_info = session.get_active_order(symbol= "SOLUSDT")
            order_status = str(order_info['result']["data"][0]['order_status'])
            print(order_status)
            print("----------------------------------------------------------------------")

            if order_status not in ["Filled"]: 
                try:
                    cancel_order = session.cancel_all_active_orders(symbol= "SOLUSDT")
                    print(cancel_order)
                    open_position= False
                except: 
                    print("No orders need to be cancelled")

    
    while open_position:
        df = get5minutedata()
        apply_technicals(df)
        print(f"Buyprice: {buyprice_limit}" + '               Close: ' + str(df.Close.iloc[-1]))
        print(f'Target: ' + str(tp) + "                  Stop: " + str(sl))
        print(f"RSI: {round(df.RSI.iloc[-1], 2)}  K: {round(df.K.iloc[-1], 2)}  D: {round(df.D.iloc[-1], 2)}")
        print(f"K > D: {round(df.K.iloc[-1], 2) > round(df.D.iloc[-1], 2)}")
        print("---------------------------------------------------")

        if df.Close[-1] <= sl:
            print("Closed Position")
            open_position = False
            send_email("SOL Long SL")
            break

        elif df.Close[-1] >= tp: 
            print("Closed Position")
            open_position = False
            send_email("SOL Long TP")
            break
        time.sleep(20)



# In[10]:


while True: 
    strategy_long(60)
    time.sleep(30)