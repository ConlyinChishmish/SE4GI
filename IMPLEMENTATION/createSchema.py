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
    
        #table of bins
        """ 
        CREATE TABLE bin(
                bin_id SERIAL PRIMARY KEY,
                bin_date TIMESTAMP DEFAULT NOW(),
                lon DOUBLE PRECISION NOT NULL,
                lat DOUBLE PRECISION NOT NULL,
                infographic BOOLEAN NOT NULL DEFAULT 'False',
                infographic_date TIMESTAMP DEFAULT NOW(),
                geom geometry(POINT) /* i'm not sure of the correctness of this line*/
        )
        """,
    
    
    # table of the gardbage collector
        """ 
            CREATE TABLE gardbage_collector(
                personal_code SERIAL PRIMARY KEY,
                username VARCHAR(255) NOT NULL,
                password VARCHAR(255) NOT NULL
        )
        """,        
        #table of the status of the bin
        """ 
            CREATE TABLE bin_status(
                bin_id INTEGER UNIQUE NOT NULL,
                GC_code INTEGER UNIQUE NOT NULL,
                date TIMESTAMP DEFAULT NOW(),
                overfull BOOLEAN NOT NULL DEFAULT 'False',
                PRIMARY KEY(bin_id, GC_code),
                
                CONSTRAINT fk_bin
                    FOREIGN KEY(bin_id)
                        REFERENCES bin(bin_id)
                        ON DELETE SET NULL,
                CONSTRAINT fk_gc
                    FOREIGN KEY(GC_code)
                        REFERENCES gardbage_collector(personal_code)
                        ON DELETE SET NULL,
        )
        """,
        
        
        
        )

#create the connection with the database
conn = connect(connStr)
cur = conn.cursor()
for command in commands :
    cur.execute(command)
cur.close()
conn.commit()
conn.close()

#IMPORT DATA ABOUT MUNICIPALITIES
# create the table containing a list of municipalities and their postal code
#this table will be used to verify the correctness of the username during the registration of the PA

#setup db connection (generic connection path to be update with your credentials: 'postgresql://user:password@localhost:5432/mydatabase')
engine = create_engine('postgresql://postgres:r3df0x@localhost:5432/binecoDB') 

# creating the dataframe of the municipalities 
# data obtained from http://lab.comuni italiani.it/download/comuni.html
# !!NOTE: i'm using the municipality of italy because i can't find a list of australian city id

#opening the file and save it in a daframe
fileTxt = open("data/listacomuni.txt")
df_patemp = pd.read_csv(fileTxt,sep=';')
fileTxt.close()
               
#selecting only the usefull columns
df_pa = df_patemp[['Comune', 'Provincia', 'CAP']]

# write the dataframe into postgreSQL
df_pa.to_sql('pa_data', engine, if_exists = 'replace', index=False)

# CREATING THE TABLE OF THE LITTER BY USING EPICOLLECT5 DATA
#connecting to the API of epicollect5
response = requests.get('https://five.epicollect.net/api/export/entries/bineco-web-application')

# store the raw text of the response in a variable
raw_data = response.text

# parse the raw text response 
data = json.loads(raw_data)

# from JSON to Pandas DataFrame
data_df = pd.json_normalize(data['data']['entries'])
len(data_df) # for a good plot it's better to extract more then 50 lines

# from Pandas DataFrame to GeoPandas GeoDataFrame
#we add a geometry column using the numeric coordinate colums

lon = '3_Position.longitude'#NOTE they are already numeric coordinate columns 
lat = '3_Position.latitude'
data_geodf = gpd.GeoDataFrame(data_df, geometry=gpd.points_from_xy(data_df[lon], data_df[lat]))

# write the dataframe into postgreSQL
data_geodf.to_sql('litter', engine, if_exists = 'replace', index=False)

#CREATING THE DATAFRAME OF THE BIN USING THE DATE FROM OSM AND UPDATE THE TABLE OF BINS
# creating the dataframe of the bins
# data obtained from OSM

#opening the file and save it in a daframe
filegeojson = open("data/Waste_basket_Cairns.geojson")
bin_df = gpd.read_file(filegeojson)
fileTxt.close()
               
#extract the usefull columns
bin_df = bin_df['full_id','geometry']
# create the columns of longitude and latitude from the geometry attribute
bin_df['lon'] = df['geometry'].x
bin_df['lat'] = df['geometry'].y

# Copy the dataframe to keep the original intact
insert_gdf = bin_df_C.copy()

# Make a new field containing the WKB dumped from the geometry column, then turn it into a regular 
#this way should be faster 
insert_gdf["geom_wkb"] = insert_gdf["geometry"].apply(lambda x: wkb_dumps(x))

# creating the query command
insert_query = """
    INSERT INTO bin (bin_id,lon,lat, geom)
    VALUES (%(full_id)s,%(lon)s,%(lat)s, ST_GeomFromWKB(%(geom_wkb)s));
"""
#creating a list of parameters to be inserted into values
params_list = [
    {
        "full_id": i,
        "lon": row["lon"],
        "lat": row["lat"],
        "geom_wkb": row["geom_wkb"]
    } for i, row in insert_gdf.iterrows()
]

# Connect to the database and make a cursor
conn = connect(connStr)
cur = conn.cursor()

# Iterate through the list of execution parameters and apply them to an execution of the insert query
for params in params_list:
    cur.execute(insert_query, params)
cur.close()
conn.commit()
conn.close()
