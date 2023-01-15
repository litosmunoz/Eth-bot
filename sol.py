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
                                    (self.df["K"]) < 0.15, 1, 0)



# In[8]:


#The mail addresses and password
sender_address = 'pythontradingbot11@gmail.com'

#Setup the MIME
message = MIMEMultipart() 
message_SL = MIMEMultipart()
message_TP = MIMEMultipart()

# In[9]:


def strategy_long(qty, open_position = False):
    df= get5minutedata()
    apply_technicals(df)
    inst = Signals(df, 1)
    inst.decide()
    print(f'Current Time is ' + str(df.index[-1]))
    print(f'Current Close is '+ str(df.Close.iloc[-1]))
    print(f'Current RSI is ' + str(df.RSI.iloc[-1]))
    print("-----------------------------------------")
    price = round(df.Close.iloc[-1],2)
    buyprice_limit = price * 0.995
    tp = round(price * 1.04,2)
    sl = round(price * 0.98,2)


    if df.Buy.iloc[-1]:
        try: 
            mail_content = "SOL Open Long Limit Order"
            message.attach(MIMEText(mail_content, 'plain'))
            
            # Create SMTP session for sending the mail
            session_mail = smtplib.SMTP('smtp.gmail.com', 587)  # use gmail with port
            session_mail.starttls()  # enable security

            # login with mail_id and password
            session_mail.login(sender_address, sender_pass)
            text = message.as_string()
            session_mail.sendmail(sender_address, receiver_address, text)
            session_mail.quit()

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

            # Set the expiration time for the order (5 mins from now)
            expiration_time = int(time.time()) + 50

            # Wait until the expiration time
            while int(time.time()) < expiration_time:

                # Check the status of the order
                order_info = session.get_active_order(symbol= "SOLUSDT")
                order_status = str(order_info['result']["data"][0]['order_status'])
                print(order_status)
                
                # If the order has been filled or cancelled, exit the loop
                if order_status in ["Filled"]:
                    open_position = True
                    break
                elif order_status in ["Cancelled"]:
                    open_position = False 
                    break

                # Sleep for 1 second before checking the order status again
                time.sleep(10)
            

            if int(time.time()) > expiration_time:
                order_info = session.get_active_order(symbol= "SOLUSDT")
                order_status = str(order_info['result']["data"][0]['order_status'])
                print(order_status)
                print("----------------------------------------------------------------------")

                if order_status in ["New"]: 
                    cancel_order = session.cancel_all_active_orders(symbol= "SOLUSDT")
                    print(cancel_order)
        
        except: 
            print("Error")

    while open_position:
        time.sleep(20)
                   
        df = get5minutedata()
        apply_technicals(df)
        print(f"Buyprice: {buyprice_limit}" + '               Close: ' + str(df.Close.iloc[-1]))
        print(f'Target: ' + str(tp) + "                  Stop: " + str(sl))
        print(f'RSI: ' + str(df.RSI.iloc[-1]))
        print("---------------------------------------------------")

        if df.Close[-1] <= sl:
            print("Closed Position")
            open_position = False

            mail_content_SL = "SOL Long SL"
            message_SL.attach(MIMEText(mail_content_SL, 'plain'))

            # Create SMTP session for sending the mail
            session_mail = smtplib.SMTP('smtp.gmail.com', 587)  # use gmail with port
            session_mail.starttls()  # enable security

            # login with mail_id and password
            session_mail.login(sender_address, sender_pass)
            text = message_SL.as_string()
            session_mail.sendmail(sender_address, receiver_address, text)
            session_mail.quit()
            break

        elif df.Close[-1] >= tp: 
            print("Closed Position")
            open_position = False

            mail_content_TP = "SOL Long TP"
            message_TP.attach(MIMEText(mail_content_TP, 'plain'))

            # Create SMTP session for sending the mail
            session_mail = smtplib.SMTP('smtp.gmail.com', 587)  # use gmail with port
            session_mail.starttls()  # enable security
            
            # login with mail_id and password
            session_mail.login(sender_address, sender_pass)
            text = message_TP.as_string()
            session_mail.sendmail(sender_address, receiver_address, text)
            session_mail.quit()
            break


# In[10]:


while True: 
    strategy_long(75)
    time.sleep(30)