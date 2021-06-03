#CREATE THE STRUCTURE OF THE MAIN TABLES OF THE DATABASE
# import packages

import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine
from psycopg2 import ( 
        connect
)
import requests
import json

#open the configuration parameter from a txt file the table
myFile = open('dbConfig.txt')
connStr = myFile.readline()
myFile.close()


cleanup = (
        'DROP TABLE IF EXISTS pa_user CASCADE',
        'DROP TABLE IF EXISTS comments',
        'DROP TABLE IF EXISTS bins',
        'DROP TABLE IF EXISTS litter',
        'DROP TABLE IF EXISTS pa_data'
        )


#variable list containing the structures of the database
commands = (
    
        #table for the registrantion of PA
        """ 
            CREATE TABLE pa_user(
                postal_code VARCHAR(5) PRIMARY KEY,
                municipality VARCHAR(255) NOT NULL,
                password VARCHAR(255) NOT NULL  
        )
        """,
    
        #table of comments
        """ 
        CREATE TABLE comments (
                comment_id SERIAL PRIMARY KEY,
                author_id VARCHAR(5),
                created TIMESTAMP DEFAULT NOW(),
                title VARCHAR(350) NOT NULL,
                body VARCHAR(500) NOT NULL,
                FOREIGN KEY (author_id)
                    REFERENCES pa_user (postal_code)
        )
        """,
    
        #table of bins
        """ 
        CREATE TABLE bins(
                bin_id SERIAL PRIMARY KEY,
                bin_date DATE DEFAULT NOW(),
                lon DOUBLE PRECISION NOT NULL,
                lat DOUBLE PRECISION NOT NULL,
                infographic BOOLEAN NOT NULL DEFAULT 'False',
                infographic_date DATE DEFAULT NULL,
                geom GEOMETRY,
                buffer GEOMETRY,
                critical BOOLEAN NOT NULL DEFAULT 'False'
        )
        """
        )


#create the connection with the database
conn = connect(connStr)
cur = conn.cursor()
for command in cleanup :
    cur.execute(command)
for command in commands :
    cur.execute(command)
cur.close()
conn.commit()
conn.close()

#setup db connection 
#NOTE: dbConfig.txt MUST be modified with the comfiguration of your DB
# build the string for the customized engine
dbD = connStr.split()
dbD = [x.split('=') for x in dbD]
engStr = 'postgresql://'+ dbD[1][1]+':'+ dbD[2][1] + '@localhost:5432/' + dbD[0][1]

engine = create_engine(engStr)  

#IMPORT DATA FROM EPICOLLECT
# send the request to the API of Epicollect5
response = requests.get('https://five.epicollect.net/api/export/entries/bineco-web-application?per_page=100')

raw_data = response.text

# parse the raw text response 
data = json.loads(raw_data)

# from JSON to Pandas DataFrame
data_df = pd.json_normalize(data['data']['entries'])
len(data_df) # for a good plot it's better to extract more then 50 lines
# preprocessing data_df
data_df = data_df.iloc[: ,4:13].copy()
data_df.columns = ['Date_of_creation','Time_of_creation','Lytter_type',
                     'Quantity','Type_of_infrastructure','Comment','Photo','Latitude',
                     'Longitude']

# from Pandas DataFrame to GeoPandas GeoDataFrame
#we add a geometry column using the numeric coordinate colums
data_geodf = gpd.GeoDataFrame(data_df, geometry=gpd.points_from_xy(data_df.Longitude, data_df.Latitude))

# write the dataframe into postgreSQL
data_geodf.to_postgis('litter', engine, if_exists = 'replace', index=False)

#CREATING DATAFRAME FOR MUNICIPALITIES CORRESPONDING POSTCODES IN ALL AUSTRALIA
#opening the file and save it in a daframe
fileTxt = open("data/df_australia_postcode.csv")
df_au_postcode = pd.read_csv(fileTxt,sep=',')
fileTxt.close()

df_au_postcode.rename(columns = {'postcode': 'postal_code', 'long': 'lon'}, inplace = True)

#import to PostgreSQL
df_au_postcode.to_sql('pa_data', engine, if_exists = 'replace', index=False)
