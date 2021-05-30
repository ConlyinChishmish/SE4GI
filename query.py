# -*- coding: utf-8 -*-
"""
Created on Sun May 30 17:45:07 2021

@author: arya
"""
#querytemp
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

def get_dbConn():
conn = get_dbConn()

mycursor = mydb.cursor()

mycursor.execute("SELECT Litter_type* FROM db_Conn")

myresult = mycursor.fetchall()

for row in myresult:
    print(row)
    
cur.close()   
    
