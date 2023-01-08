#!/usr/bin/env python
# coding: utf-8

# In[1]:


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
    frame = pd.DataFrame(session_auth.query_kline(symbol="ETHUSDT", interval="5m")["result"])
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
    #df["D"] = df["K"].rolling(3).mean()
    df["RSI"] = ta.momentum.rsi(df.Close, window = 14)
    df.dropna(inplace=True)



# In[7]:

# Variables
rsi_enter = 77
rsi_exit = 24


# In[8]:


class Signals:
    def __init__(self, df, lags):
        self.df = df
        self.lags = lags
    
    #Checking if we have a trigger in the last n time steps
    def get_trigger(self):
        df_2 = pd.DataFrame()
        for i in range(self.lags + 1):
            mask = (self.df["RSI"].shift(i) > rsi_enter)
            df_2 = df_2.append(mask, ignore_index = True)
        return df_2.sum(axis= 0)
    
    # Is the trigger fulfilled and are all buying conditions fulfilled?
    def decide(self):
         self.df["trigger"] = np.where(self.get_trigger(), 1, 0)
         self.df["Sell"]= np.where((self.df.trigger), 1, 0)



# In[9]:


#The mail addresses and password
sender_address = 'pythontradingbot11@gmail.com'

#Setup the MIME
message = MIMEMultipart() 
message_SL = MIMEMultipart()
message_TP = MIMEMultipart()
message_RSI = MIMEMultipart()
message_Others = MIMEMultipart()


# In[10]:


def strategy_short(qty, open_position = False):
    df= get5minutedata()
    apply_technicals(df)
    inst = Signals(df, 1)
    inst.decide()
    print(f'Current Time is ' + str(df.index[-1]))
    print(f'Current Close is '+str(df.Close.iloc[-1]))
    print(f'Current RSI is ' + str(df.RSI.iloc[-1]))
    print("-----------------------------------------")
    buyprice = round(df.Close.iloc[-1],2)
    tp = round(buyprice * 0.93,2)
    sl = round(buyprice * 1.03,2)

    if df.Sell.iloc[-1]:
        try: 
            mail_content = "ETH Open Short"
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

            print(f"Buyprice: {buyprice}")

            print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")

            order = session.place_active_order(symbol="ETHUSDT",
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
        except:
            time.sleep(20)

            print("-----------------------------------------")

            print(f"Buyprice: {buyprice}")

            print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")

            order = session.place_active_order(symbol="ETHUSDT",
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
        time.sleep(30)
                            
        df = get5minutedata()
        apply_technicals(df)
        print(f"Buyprice: {buyprice}" + '             Close: ' + str(df.Close.iloc[-1]))
        print(f'Target: ' + str(tp) + "               Stop: " + str(sl))
        print(f'RSI Target: 24' + '                RSI: ' + str(df.RSI.iloc[-1]))
        print("---------------------------------------------------")

        if df.Close[-1] >= sl:
            print("Closed Position")
            open_position = False

            mail_content_SL = "ETH Short SL"
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

        elif df.Close[-1] <= tp: 
            print("Closed Position")
            open_position = False

            mail_content_TP = "ETH Short TP"
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

        elif df.RSI[-1] < rsi_exit:
            
            try: 
                print(session.place_active_order(symbol="ETHUSDT",
                                                side="Buy",
                                                order_type="Market",
                                                qty= qty,
                                                time_in_force="GoodTillCancel",
                                                reduce_only=True,
                                                close_on_trigger=False))  

                print("---------------------------------------------------")
                print("Closed position")
                open_position = False
                mail_content_RSI = "ETH Short Closed - RSI < 24"
                message_RSI.attach(MIMEText(mail_content_RSI, 'plain'))

                # Create SMTP session for sending the mail
                session_mail = smtplib.SMTP('smtp.gmail.com', 587)  # use gmail with port
                session_mail.starttls()  # enable security

                # login with mail_id and password
                session_mail.login(sender_address, sender_pass)
                text = message_RSI.as_string()
                session_mail.sendmail(sender_address, receiver_address, text)
                session_mail.quit()
                break

            except: 
                print("Position already closed")
                open_position = False
                
                mail_content_Others = "Position Closed"
                message_Others.attach(MIMEText(mail_content_Others, 'plain'))

                # Create SMTP session for sending the mail
                session_mail = smtplib.SMTP('smtp.gmail.com', 587)  # use gmail with port
                session_mail.starttls()  # enable security

                # login with mail_id and password
                session_mail.login(sender_address, sender_pass)
                text = message_Others.as_string()
                session_mail.sendmail(sender_address, receiver_address, text)
                session_mail.quit()
                break


# In[11]:


while True: 
    strategy_short(0.7)
    time.sleep(30)






