#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import numpy as np
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pybit import spot  # <-- import HTTP & WSS for spot
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


# In[4]:


#Establishing Connection with the API (SPOT)
from pybit import spot
session_auth = spot.HTTP(
    endpoint='https://api.bybit.com',
    api_key = api_key_pw,
    api_secret= api_secret_pw
)


# In[5]:


#This function gets Real BTC Price Data and creates a smooth dataframe that refreshes every 15 minutes
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


class Signals:
    def __init__(self, df, lags):
        self.df = df
        self.lags = lags
    
    #Checking if we have a trigger in the last n time steps
    def get_trigger(self):
        df_2 = pd.DataFrame()
        for i in range(self.lags + 1):
            mask = (self.df["RSI"].shift(i) > 75)
            df_2 = df_2.append(mask, ignore_index = True)
        return df_2.sum(axis= 0)
    
    # Is the trigger fulfilled and are all buying conditions fulfilled?
    def decide(self):
         self.df["trigger"] = np.where(self.get_trigger(), 1, 0)
         self.df["Sell"]= np.where((self.df.trigger), 1, 0)



# In[8]:


#The mail addresses and password
sender_address = 'pythontradingbot11@gmail.com'
sender_pass = os.getenv('mail_key')
receiver_address = 'carlos.mfresco@gmail.com'
#Setup the MIME
message = MIMEMultipart() 
message_SL = MIMEMultipart()
message_TP = MIMEMultipart()
message_RSI = MIMEMultipart()
message_Others = MIMEMultipart()


# In[9]:


def strategy_short(qty, open_position = False):
    df= get5minutedata()
    apply_technicals(df)
    inst = Signals(df, 1)
    inst.decide()
    print(f'Current Close is '+str(df.Close.iloc[-1]))
    print(f'Current RSI is ' + str(df.RSI.iloc[-1]))
    print("-----------------------------------------")

    if df.Sell.iloc[-1]:
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

        from pybit import usdt_perpetual
        session = usdt_perpetual.HTTP(
        endpoint='https://api.bybit.com',
        api_key = api_key_pw,
        api_secret= api_secret_pw)

        buyprice = round(df.Close.iloc[-1],2)

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
                                                take_profit = round(buyprice * 0.93,2),
                                                stop_loss = round(buyprice * 1.03,2))
        print(order)

        eth_order_id = str(order['result']['order_id'])
        print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        print(f"Order id: {eth_order_id}") 
        print("-------------------------------------------------")

        open_position = True
        
    while open_position:
        time.sleep(30)
        from pybit import spot
        session_auth = spot.HTTP(
            endpoint='https://api.bybit.com',
            api_key = api_key_pw,
            api_secret= api_secret_pw)
            
        df = get5minutedata()
        apply_technicals(df)
        print(f"Buyprice: {buyprice}" + '                Close: ' + str(df.Close.iloc[-1]))
        print(f'Target: ' + str(round(buyprice * 0.93, 2)) + "                 Stop: " + str(round(buyprice * 1.03, 2)))
        print(f'RSI Target: 25' + '                RSI: ' + str(df.RSI.iloc[-1]))
        print("---------------------------------------------------")

        if df.Close[-1] > buyprice* 1.03:
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

        elif df.Close[-1] < buyprice * 0.93: 
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

        elif df.RSI[-1] < 25:
            session = usdt_perpetual.HTTP(
            endpoint='https://api.bybit.com',
            api_key = api_key_pw,
            api_secret= api_secret_pw)

            try: 
                print(session.place_active_order(symbol="ETHUSDT",
                                                side="Buy",
                                                order_type="Market",
                                                qty= qty,
                                                time_in_force="GoodTillCancel",
                                                reduce_only=True,
                                                close_on_trigger=False))            
            
                print("Closed position")
                open_position = False
                mail_content_RSI = "ETH Short Closed - RSI < 25"
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


# In[10]:


while True: 
    strategy_short(0.5)
    time.sleep(60)





