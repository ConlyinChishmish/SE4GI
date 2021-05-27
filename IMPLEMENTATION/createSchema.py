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
import datetime

#open the configuration parameter from a txt file the table
myFile = open('dbConfig.txt')
connStr = myFile.readline()
myFile.close()


cleanup = (
        'DROP TABLE IF EXISTS pa_user CASCADE',
        'DROP TABLE IF EXISTS comments',
        'DROP TABLE IF EXISTS bin_cairns',
        'DROP TABLE IF EXISTS bin_townsville',
        'DROP TABLE IF EXISTS litter'
        )


#variable list containing the structures of the database
commands = (
    
        #table for the registrantion of PA
        """ 
            CREATE TABLE pa_user(
                postcode VARCHAR(5) PRIMARY KEY,
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
                    REFERENCES pa_user (postcode)
        )
        """,
    
        #table of bins
        """ 
        CREATE TABLE bin_cairns(
                bin_id SERIAL PRIMARY KEY,
                bin_date DATE DEFAULT NOW(),
                lon DOUBLE PRECISION NOT NULL,
                lat DOUBLE PRECISION NOT NULL,
                infographic BOOLEAN NOT NULL DEFAULT 'False',
                infographic_date DATE DEFAULT NULL,
                geom geometry(POINT)
        )
        """,
    
        #table of bins
        """ 
        CREATE TABLE bin_townsville(
                bin_id SERIAL PRIMARY KEY,
                bin_date DATE DEFAULT NOW(),
                lon DOUBLE PRECISION NOT NULL,
                lat DOUBLE PRECISION NOT NULL,
                infographic BOOLEAN NOT NULL DEFAULT 'False',
                infographic_date DATE DEFAULT NULL,
                geom geometry(POINT)
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

#setup db connection (generic connection path to be update with your credentials: 'postgresql://user:password@localhost:5432/mydatabase')
engine = create_engine('postgresql://postgres:jawadamp@localhost:5432/binecoDB') 

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

#CREATING THE DATAFRAME OF THE BIN USING THE DATE FROM OSM AND UPDATE THE TABLE OF BINS

#Town of CAIRNS
#opening the file and save it in a daframe
filegeojson_cairns = open("data/Waste_basket_Cairns.geojson")
binCairns_gdf = gpd.read_file(filegeojson_cairns)
filegeojson_cairns.close()
#extract the usefull columns
binCairns_gdf = binCairns_gdf[['full_id','geometry']]
#rename id
for i in range(len(binCairns_gdf)):
    binCairns_gdf.loc[i,'full_id'] = i
# create the columns of longitude and latitude from the geometry attribute
binCairns_gdf['lon'] = binCairns_gdf['geometry'].x
binCairns_gdf['lat'] = binCairns_gdf['geometry'].y
# create the columns of datetime and set it
binCairns_gdf['date'] = datetime.datetime(2018, 5, 1)
#import to PostgreSQL
binCairns_gdf.to_postgis('cairns_temp', engine, if_exists = 'replace', index=False)

#Town of TOWNSVILLE
#opening the file and save it in a daframe
filegeojson_townsville = open("data/Waste_basket_Townsville.geojson")
binTownsville_gdf = gpd.read_file(filegeojson_townsville)
filegeojson_townsville.close()
#extract the usefull columns
binTownsville_gdf = binTownsville_gdf[['full_id','geometry']]
#rename id 
for i in range(len(binTownsville_gdf)):
    binTownsville_gdf.loc[i,'full_id'] = i
# create the columns of longitude and latitude from the geometry attribute
binTownsville_gdf['lon'] = binTownsville_gdf['geometry'].x
binTownsville_gdf['lat'] = binTownsville_gdf['geometry'].y
# create the columns of datetime and set it
binTownsville_gdf['date'] = datetime.datetime(2018, 5, 1)
#import in PostgreSQL
binTownsville_gdf.to_postgis('townsville_temp', engine, if_exists = 'replace', index=False)

# creating the query command to insert data into DB original bins' tables from temporary bins' table
insert_query = ("""
    INSERT INTO bin_cairns (bin_id,lon,lat,geom,bin_date)
    SELECT full_id,lon,lat,geometry,date FROM cairns_temp;
    """,
    """
    INSERT INTO bin_townsville (bin_id,lon,lat,geom,bin_date)
    SELECT full_id,lon,lat,geometry,date FROM townsville_temp;
    """)
# drop temporary bins' tables
cleanup_temp = (
        'DROP TABLE IF EXISTS cairns_temp',
        'DROP TABLE IF EXISTS townsville_temp'
        )

# Connect to the database and make a cursor
conn = connect(connStr)
cur = conn.cursor()

# Execution of the insert query and clean up of temporary tables
for command in insert_query :
    cur.execute(command)
for command in cleanup_temp :
    cur.execute(command)
    
cur.close()
conn.commit()
conn.close()

#CREATING DATAFRAME FOR MUNICIPALITIES CORRESPONDING POSTCODES IN ALL AUSTRALIA
#opening the file and save it in a daframe
fileTxt = open("data/df_australia_postcode.csv")
df_au_postcode = pd.read_csv(fileTxt,sep=',')
fileTxt.close()

#select useful columns
df_au_postcode = df_au_postcode.iloc[:, 2:4]

#import to PostgreSQL
df_au_postcode.to_sql('pa_data', engine, if_exists = 'replace', index=False)
