from flask import (
    Flask, render_template, request, redirect, flash, url_for, session, g
)

from werkzeug.security import check_password_hash, generate_password_hash

from werkzeug.exceptions import abort

from psycopg2 import (
        connect
)

from sqlalchemy import create_engine 

from shapely import geometry
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon  

import numpy as np
from numpy import array


import pyproj
from shapely.ops import transform
from functools import partial

import pandas as pd
import geopandas as gpd
import osmnx as ox
import matplotlib.pyplot as plt
import datetime 

import InteractiveMap as im

# Create the application instance
app = Flask(__name__, template_folder="templates")
# Set the secret key to some random bytes. Keep this really secret!
app.secret_key = '_5#y2L"F4Q8z\n\xec]/'                                                                   

def customized_engine(): #NOTE: dbConfig.txt MUST be modified with the comfiguration of your DB
    # build the string for the customized engine
    #open the configuration parameter from a txt file the table
    myFile = open('dbConfig.txt')
    connStr = myFile.readline()
    myFile.close()
    
    dbD = connStr.split()
    dbD = [x.split('=') for x in dbD]
    engStr = 'postgresql://'+ dbD[1][1]+':'+ dbD[2][1] + '@localhost:5432/' + dbD[0][1]

    return create_engine(engStr)

def get_dbConn():
    if 'dbConn' not in g:
        myFile = open('dbConfig.txt')
        connStr = myFile.readline()
        g.dbConn = connect(connStr)
    
    return g.dbConn

def close_dbConn():
    if 'dbConn' in g:
        g.dbComm.close()
        g.pop('dbConn')
 
#function that explode multypoligons of city boundaries gdf into polygons
def explode(indf):
    outdf = gpd.GeoDataFrame(columns=indf.columns)
    for idx, row in indf.iterrows():
        if type(row.geometry) == Polygon:
            outdf = outdf.append(row,ignore_index=True)
        if type(row.geometry) == MultiPolygon:
            multdf = gpd.GeoDataFrame(columns=indf.columns)
            recs = len(row.geometry)
            multdf = multdf.append([row]*recs,ignore_index=True)
            for geom in range(recs):
                multdf.loc[geom,'geometry'] = row.geometry[geom]
            outdf = outdf.append(multdf,ignore_index=True)
    return outdf

#function for retrieving PA boundaries data from OSM                                               
def cityBoundary(locality):                                  
    locality =  locality + ", Australia"
    tags = {"boundary": "administrative"}
    boundaryOSM = ox.geometries_from_place(locality, tags)
    boundary_gdf = gpd.GeoDataFrame(boundaryOSM)
    #extract useful columns
    boundary_gdf = boundary_gdf.iloc[:, 0:10:9]
    #explode multypoligons in polygons 
    boundary_gdf=explode(boundary_gdf)
    #searching for boundaries referring to PA
    query_search ='short_name == "Cairns"'
    global city_boundaries 
    city_boundaries = boundary_gdf.query(query_search)
    city_boundaries = city_boundaries.reset_index(drop=True)
    return
 
#creating the function for computing buffer around bins
def geodesic_point_buffer(lat, lon, radius):
    local_azimuthal_projection = "+proj=aeqd +R=6371000 +units=m +lat_0={} +lon_0={}".format(lat, lon)
    wgs84_to_aeqd = partial(pyproj.transform, pyproj.Proj("+proj=longlat +datum=WGS84 +no_defs"), pyproj.Proj(local_azimuthal_projection),)
    aeqd_to_wgs84 = partial(pyproj.transform, pyproj.Proj(local_azimuthal_projection), pyproj.Proj("+proj=longlat +datum=WGS84 +no_defs"),)
    center = Point(float(lon), float(lat))
    point_transformed = transform(wgs84_to_aeqd, center)
    buffer = point_transformed.buffer(radius)
    # Get the polygon with lat lon coordinates
    circle_poly = transform(aeqd_to_wgs84, buffer)
    return circle_poly

#creating the function for configurating bins table according to registered PA (we retrieve data from OSM)
def binsTable(locality):   #call this function in registration if it is made correctly bin_table(municipality)
    locality =  locality + ", Australia"
    tags = {'amenity': 'waste_basket'}
    binsOSM = ox.geometries_from_place(locality, tags)
    bins_gdf = gpd.GeoDataFrame(binsOSM)

    # create the columns of longitude and latitude from the geometry attribute
    bins_gdf['lon'] = bins_gdf['geometry'].x
    bins_gdf['lat'] = bins_gdf['geometry'].y
    # create the columns of datetime and set it
    bins_gdf['date'] = datetime.datetime(2018, 5, 1)
    bins_gdf['buffer'] = None
	

    #adding buffer attribute
    for i, row in bins_gdf.iterrows():
        bins_gdf.loc[i, 'buffer'] = geodesic_point_buffer(bins_gdf.loc[i, 'lat'], bins_gdf.loc[i, 'lon'], 500.0)

    #setup db connection 
    engine = customized_engine()
	
    #import in PostgreSQL
    bins_gdf.to_postgis('bins_temp', engine, if_exists = 'replace', index=False)

    #add data to DB bins table using the temporary table
    conn = get_dbConn()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO bins (lon,lat,geom,bin_date,buffer) SELECT lon,lat,geometry,date,buffer FROM bins_temp'
    )
    cur.execute(
        'DROP TABLE IF EXISTS bins_temp'
    )
    cur.close()
    conn.commit()
    conn.close()
    
    return


 #registration
@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        postal_code = request.form['postal_code']
        municipality = request.form['municipality']
        password = request.form['password']
        error = None

        if not postal_code:
            error = 'postal_code is required.'
        elif not password:
            error = 'Password is required.'
        elif not municipality:
            error = 'municipality is required.'
        else:
            conn = get_dbConn()
            cur = conn.cursor()
            #checking if the postal code has already an account
            cur.execute('SELECT postal_code FROM pa_user WHERE postal_code = %s', (postal_code,))
            if cur.fetchone() is not None:
                error = 'User {} is already registered.'.format(postal_code)
                cur.close()
            else:
                #checking if the postal code exist in australia database
                cur.execute('SELECT postal_code FROM pa_data WHERE postal_code = %s', (postal_code,))
                if cur.fetchone() is None:
                    error = 'postal_code {} does not exist'.format(postal_code)
                    cur.close()
                #checking if the municipality code exist in australia database  
                cur.execute('SElECT locality FROM pa_data WHERE locality = %s', (municipality,))
                if cur.fetchone() is None:
                    error = 'municipality {} does not exist'.format(municipality)
                    cur.close()
		        #check if municipality and postal code correspond
                #else:
                 # cur.execute('SELECT pa_data.locality FROM pa_data WHERE postal_code = %s', (postal_code,))
                  #if (cur.fetchone() != municipality):
                    #error = '{} and {} do not correspond'.format(postal_code,municipality)
                     #cur.close()

        if error is None:
            conn = get_dbConn()
            cur = conn.cursor()
            cur.execute(
                'INSERT INTO pa_user (postal_code,municipality,password) VALUES (%s, %s, %s)',
                (postal_code, municipality, generate_password_hash(password))
            )
            cur.close()
            conn.commit()
	
            binsTable(municipality) 
            cityBoundary(municipality)
            return redirect(url_for('login'))
        flash(error)

    return render_template('auth/register.html')

#login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        postal_code = request.form['postal_code']
        password = request.form['password']
        conn = get_dbConn()
        cur = conn.cursor()
        error = None
        cur.execute(
            'SELECT * FROM pa_user WHERE postal_code = %s', (postal_code,)
        )
        user = cur.fetchone()
        cur.close()
        conn.commit()
        
        if user is None:
            error = 'Incorrect postal code.'
        elif not check_password_hash(user[2],password):
            error = 'Incorrect password.'
        
        if error is None:
            session.clear()
            session['user_id'] = user[0]
            return redirect(url_for('index'))
        flash(error)
    
    return render_template('auth/login.html')

#logout
@app.route('/logout')
def logout():
    # remove the username from the session if it's there
    session.clear()
    return redirect(url_for('index'))
 
# "cookies"
def load_logged_in_user():
    postal_code = session.get('user_id')

    if postal_code is None:
        g.user = None
    else:
        conn = get_dbConn()
        cur = conn.cursor()
        cur.execute(
            'SELECT * FROM pa_user WHERE postal_code = %s', (postal_code,)
        )
        g.user = cur.fetchone()
        cur.close()
        conn.commit()
    if g.user is None:
        return False
    else: 
        return True
    
# Create a URL route in our application for "/"
@app.route('/')
@app.route('/index')
def index():
    if load_logged_in_user():
        return render_template('indexlogged.html')
    else:
        return render_template('index.html')

# UC.3 Pa enters new data about the bin
@app.route('/new_bin', methods=('GET', 'POST'))
def new_bin():
    if load_logged_in_user():
        if request.method == 'POST' :
            lon = request.form['lon']
            lat = request.form['lat']
        
            geom = Point(float(lon), float(lat))
            buffer = geodesic_point_buffer(lat, lon, 500.0)
            error = None
       
            # check if the data inserted are correct
            if (not lon or not lat):
                error = '*this data is required!'
            elif(float(lat)< -90 or float(lat)>90):
                error ='Please insert a valid value for the latitude -90<= lat <=90'
            elif(float(lon)<0 or float(lon)>=360):
                error ='Please insert a valid value for the longitude 0<= lon <360'
         
            #check if something went wrong in compiling the form  
            if error is not None :
                flash(error)
                return redirect(url_for('new_bin'))
            #everything in the form is ok, database connection is allowed
            else : 
                data = [[lon,lat,geom,buffer]]
                bin_gdf = gpd.GeoDataFrame(data,columns = ['lon','lat','geometry','buffer'])
                engine = customized_engine()
                bin_gdf.to_postgis('bin_temp', engine, if_exists = 'replace', index=False)
            
                conn = get_dbConn()
                cur = conn.cursor()
                cur.execute(
                        'INSERT INTO bins (lon,lat,geom,buffer) SELECT cast(lon as double precision),cast(lat as double precision),geometry,buffer FROM bin_temp'
                        )
                cur.execute(
                        'DROP TABLE IF EXISTS bin_temp'
                        )
                cur.close()
                conn.commit()
                return redirect(url_for('index'))
        else :
            return render_template('new_bin.html')          
    else:
        error = 'Only loggedin users can updaete bins!'
        flash(error)
        return redirect(url_for('interactive_map'))
    
    
#global variable constant values   
global threshold 
threshold = np.array([0.6,0.5,0.3,0.2]) #threshold for low-medium-high-none
#for none, if none absolute frequency overcomes the threshold (>=0.2) is not necessary to put a bin/infographic
#for low-medium-high if frequencies overcome the corresponding thresholds a bin/infographic has to be put 

# query by temporal window
def query_temp():
    engine = customized_engine()
    gdf_litt = gpd.GeoDataFrame.from_postgis('litter', engine, geom_col='geometry')
    # cast on the data column
    gdf_litt['Date_of_creation'] = pd.to_datetime(gdf_litt['Date_of_creation'], format='%d/%m/%Y')
    # find the last entry in the dataframe
    last_date = max(gdf_litt['Date_of_creation'])
    # compute the 30 days starting from the last entry date
    start_date= last_date - datetime.timedelta(30)
    # filter the data of litter with the date
    filtered_litter = gdf_litt[(gdf_litt.Date_of_creation >= start_date) & (gdf_litt.Date_of_creation <= last_date)]
    
    return filtered_litter

# query by area function
def query_by_area(area):
    engine = customized_engine()
    # putting all the points into a geodataframe
    gdf_litt = gpd.GeoDataFrame.from_postgis('litter', engine, geom_col='geometry')
    # select the points contained in the area
    filtered_litter = gdf_litt[gdf_litt.geometry.within(area)]
    
    return filtered_litter

@app.route('/interactive_map', methods=('GET'))          
def map_function():  
    if load_logged_in_user():
        im.interactive_map()
        return render_template('interactive_map.html')
    else:
        error = 'Only loggedin users can visualise map!'
        flash(error)
        return redirect(url_for('login'))

@app.route('/create_image', methods=('GET', 'POST'))          
def create_image():  
    if load_logged_in_user():
        if request.method == 'POST':
            bin_id = request.form['bin_id']
            error = None
            if not bin_id:
                error = 'Bin id is required!'
            if error is not None:
                flash(error)
                return redirect(url_for('create_image'))
            else: 
                Bin = get_bin(bin_id)
                area = Bin[7]          
                data_geodf = query_by_area(area)
                #if there is no litter point in bin's buffer flash error 
                if data_geodf.empty:     
                    error = "There is no litter point in bin's buffer!"
                    flash(error)
                    return redirect(url_for('indexlogged'))
                results = statistycal_analysis(data_geodf,bin_id)
                #array for the x axis
                val = array(['low','medium','high','none'])
                col = array(['lightsteelblue', 'gold', 'saddlebrown', 'k'])
                plt.bar(val,results, color = col)
                for i in range(4):
                    plt.axhline(y=threshold[i], color= col[i])
                plt.ylim(0,1)
                plt.title("Absolute frequency of quantiy and its threshold")
                plt.legend(val,title='Legend', bbox_to_anchor=(1.05, 1), loc='upper left')
                #save the plot in a image
                plt.savefig('/static/plot_image.eps', format='eps')
                return redirect(url_for('visualise_results'))
        else:
            return render_template('create_image.html')
    else:
        error = 'Only loggedin users can visualise results!'
        flash(error)
        return redirect(url_for('interactive_map'))
    
    
@app.route('/visualiseResults', methods=('GET', 'POST'))
def visualize_results(): 
    if load_logged_in_user():
        return render_template('visualiseResults.html')
    else:
        error = 'Only loggedin users can visualise results!'
        flash(error)
        return redirect(url_for('interactive_map'))

#function that computes statistical analysis of litter data contained in a certain bin's buffer
def statistycal_analysis(data_geodf,id):
    #if there is no litter point in bin's buffer return 
    if data_geodf.empty:       
        return                                                                                                                           
	#data_geodf geodataframe with litter data contained in the selected area (or buffer)
	#change quantity into numeric values to compute daily mean
    for i, row in data_geodf.iterrows():
        if data_geodf.loc[i, 'Quantity'] == "Low":                       
            data_geodf.loc[i, 'Quantity'] = "1"
        elif data_geodf.loc[i, 'Quantity'] == "Medium":
            data_geodf.loc[i, 'Quantity'] = "2"
        elif data_geodf.loc[i, 'Quantity'] == "High":
            data_geodf.loc[i, 'Quantity'] = "3"
    data_geodf['Quantity'] = pd.to_numeric(data_geodf['Quantity'])
    print(data_geodf)
	#create a new dataframe with data grouped by date of creation and compute the mean according to the Quantity attribute
	#we obtain a dataframe with two columns, one for Date_of_creation and one for quantity's mean, each row corresponds to a certain Date_of_creation
    daily_df = data_geodf.groupby(['Date_of_creation'])['Quantity'].mean().reset_index(name='Quantity_daily_mean')
	#assign string type values "low"-"medium"-"high" to daily_df quantity means
    for i, row in daily_df.iterrows():
        if daily_df.loc[i, 'Quantity_daily_mean'] <= 1.5:
            daily_df.loc[i, 'Quantity_daily_mean'] = "Low"
        elif daily_df.loc[i, 'Quantity_daily_mean'] >= 1.5 and daily_df.loc[i, 'Quantity_daily_mean'] <= 2.5:
            daily_df.loc[i, 'Quantity_daily_mean'] = "Medium"
        elif daily_df.loc[i, 'Quantity_daily_mean'] >= 2.5:
            daily_df.loc[i, 'Quantity_daily_mean'] = "High"
	#compute absolute frequences of the various quantity over 30 days (sum of each type of quantity / 30 days)
	#first count the amount of low-medium-high quantity
    frequency_df = daily_df.groupby(['Quantity_daily_mean'])['Quantity_daily_mean'].count().reset_index(name='Count')
	#then calculate absolute frequency
    frequency_df['Absolute_frequency']=None                                                     
    for i, row in frequency_df.iterrows():
        frequency_df.loc[i, 'Absolute_frequency'] = frequency_df.loc[i, 'Count']/30
	#compute none frequency
    	#compute none frequency
    none_quantity = 'none'
    none_count = 30-(frequency_df['Count'].sum())
    none_frequency = 1-(frequency_df['Absolute_frequency'].sum())
    
    frequency_df.loc[frequency_df.index.max()+1] = [none_quantity, none_count, none_frequency]
	#order rows according to quantity
    frequency_df['Quantity_daily_mean'] = pd.Categorical(frequency_df['Quantity_daily_mean'],categories=['low','medium','high','none'])
    frequency_df = frequency_df.sort_values('Quantity_daily_mean', ignore_index=True)
	
	#if bin is not contained in the area return array of absolute frequencies
    absolute_frequency_df = frequency_df.loc[:, 'Absolute_frequency']
    absolute_frequency_array = np.array(absolute_frequency_df).reshape(-1)
    return absolute_frequency_array 


# find bin by id
def get_bin(id):
    conn = get_dbConn()
    cur = conn.cursor()
    cur.execute(
        """SELECT *
           FROM bins
           WHERE bins.bin_id = %s""",
        (id,)
    )
    Bin = cur.fetchone()
    cur.close()
    if Bin is None:
        abort(404, "Bin id {0} doesn't exist.".format(id))
    return Bin

# update bin
@app.route('/<int:id>/update_bin', methods=('GET', 'POST'))
def update_bin(id):
    if load_logged_in_user():
        Bin= get_bin(id)
        if request.method == 'POST' :
            infographic= request.form['infographic']
            error = None
            
            if not infographic :
                error = 'infographic is required is required!'
            if error is not None :
                flash(error)
                return redirect(url_for('update_bin'))
            else : 
                conn = get_dbConn()
                cur = conn.cursor()
                cur.execute('UPDATE bins SET infografic = %s'
                               'WHERE bin_id = %s', 
                               (infographic, id)
                               )
                cur.close()
                conn.commit()
                return redirect(url_for('index'))
        else :
            return render_template('update_bin.html', Bin = Bin)
    else:
        error = 'Only loggedin users can updaete bins!'
        flash(error)
        return redirect(url_for('interactive_map'))

#COMMENT SECTION	
@app.route('/help_us')
def help_us():
	
    conn = get_dbConn()   
    cur = conn.cursor()
    cur.execute(
            """SELECT c.comment_id, p.postal_code, c.created, c.title, c.body 
               FROM pa_user AS p, comments AS c WHERE  
                    p.postal_code = c.author_id"""
                    )
    comments = cur.fetchall()
    cur.close()
    conn.commit()
    load_logged_in_user()
    return render_template('help_us/index_help.html', comments=comments)

@app.route('/createComment', methods=('GET', 'POST'))
def create_comment():
    if load_logged_in_user():
        if request.method == 'POST' :
            title = request.form['title']
            body = request.form['body']
            error = None
            
            if not title :
                error = 'Title is required!'
            if error is not None :
                flash(error)
                return redirect(url_for('createComment'))
            else : 
                conn = get_dbConn()
                cur = conn.cursor()
                cur.execute('INSERT INTO comments (title, body, author_id) VALUES (%s, %s, %s)', 
                            (title, body, g.user[0])
                            )
                cur.close()
                conn.commit()
                return redirect(url_for('help_us'))
        else :
            return render_template('help_us/createComment.html')
    else :
        error = 'Only logged in users can insert comments!'
        flash(error)
        return redirect(url_for('login'))
   
def get_comment(id):
    conn = get_dbConn()
    cur = conn.cursor()
    cur.execute(
        """SELECT *
           FROM comments
           WHERE comments.comment_id = %s""",
        (id,)
    )
    comment = cur.fetchone()
    cur.close()
    if comment is None:
        abort(404, "Comment id {0} doesn't exist.".format(id))

    if comment[1] != g.user[0]:
        abort(403)  #access is forbidden 

    return comment

@app.route('/<int:id>/updateComment', methods=('GET', 'POST'))
def update_comment(id):
    if load_logged_in_user():
        comment = get_comment(id)
        if request.method == 'POST' :
            title = request.form['title']
            body = request.form['body']
            error = None
            
            if not title :
                error = 'Title is required!'
            if error is not None :
                flash(error)
                return redirect(url_for('update_Comment'))
            else : 
                conn = get_dbConn()
                cur = conn.cursor()
                cur.execute('UPDATE comments SET title = %s, body = %s'
                               'WHERE comment_id = %s', 
                               (title, body, id)
                               )
                cur.close()
                conn.commit()
                return redirect(url_for('help_us'))
        else :
            return render_template('help_us/updateComment.html', comment = comment)
    else :
        error = 'Only loggedin users can insert comments!'
        flash(error)
        return redirect(url_for('login'))

@app.route('/<int:id>/deleteComment', methods=('POST',))
def delete_comment(id):
    conn = get_dbConn()                
    cur = conn.cursor()
    cur.execute('DELETE FROM comments WHERE comment_id = %s', (id,))
    conn.commit()
    return redirect(url_for('help_us'))        
        
        
if __name__ == '__main__':
    app.run(debug=True) 
	
