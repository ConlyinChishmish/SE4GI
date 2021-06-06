from flask import (
    g
)
from psycopg2 import (
        connect
)
import geopandas as gpd
import pandas as pd
import datetime
import numpy as np

from sqlalchemy import create_engine

from bokeh.plotting import figure, show, output_file
from bokeh.models import ColumnDataSource, LabelSet, HoverTool, OpenURL
from bokeh.models.tools import TapTool
from bokeh.tile_providers import get_provider, Vendors
from bokeh.io import output_notebook
from bokeh.layouts import row
output_notebook ()

def get_dbConn():
    if 'dbConn' not in g:
        myFile = open('dbConfig.txt')
        connStr = myFile.readline()
        g.dbConn = connect(connStr)
    
    return g.dbConn

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

#create a function to extract coordinates from the geodataframe
def getPointCoords(rows, geom, coord_type):
#Calculates coordinates ('x' or 'y') of a Point geometry
    if coord_type == 'x':
        return rows[geom].x
    elif coord_type == 'y':
        return rows[geom].y

# query by area function
def query_by_area(area):
    litt_temp = query_temp()
    # select the points contained in the area
    filtered_litter = litt_temp[litt_temp.geometry.within(area)]
    
    return filtered_litter

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

#function that computes statistical analysis of litter data contained in a certain bin's buffer
def statistycal_analysis(data_geodf,id_bin):
    #if there is no litter point in bin's buffer return 
    if data_geodf.empty:       
        return                                                                                                                           
	#data_geodf geodataframe with litter data contained in the selected area (or buffer)
	#change quantity into numeric values to compute daily mean
    for i, r in data_geodf.iterrows():
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
    for i, r in daily_df.iterrows():
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
    for i, r in frequency_df.iterrows():
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

threshold = np.array([0.6,0.5,0.3,0.2,0.7]) #threshold for low-medium-high-none
#for none, if none absolute frequency overcomes the threshold (>=0.2) is not necessary to put a bin/infographic
#for low-medium-high if frequencies overcome the corresponding thresholds a bin/infographic has to be put 

def critical(data_gdf,id_bin):
    #if there is no litter point in bin's buffer return 
    if data_gdf.empty:       
        return  
    absolute_frequency_array = statistycal_analysis(data_gdf,id_bin)
    if absolute_frequency_array[3] >= threshold[4]:
        infographic = False
    elif absolute_frequency_array[3] <= threshold[3]:
        infographic = True 
    elif absolute_frequency_array[2] >= threshold[2]:
        infographic = True 
    elif absolute_frequency_array[1] >= threshold[1]:
        infographic = True 
    elif absolute_frequency_array[0] >= threshold[0]:
        infographic = True 
    else:
        infographic = False
    id_bin = int(id_bin)
    conn = get_dbConn()
    cur = conn.cursor()
    cur.execute('UPDATE bins SET critical = %s WHERE bin_id = %s', (infographic, id_bin))
    cur.close()
    conn.commit()
    return

def interactive_map(city_boundaries):
	
    engine = customized_engine()

    bins_gdf = gpd.GeoDataFrame.from_postgis('bins', engine, geom_col='geom')
    t_srs = 4326
    bins_gdf.set_geometry('geom', crs=(u'epsg:'+str(t_srs)), inplace=True)
    
    bins_buffer_gdf = gpd.GeoDataFrame.from_postgis('bins', engine, geom_col='buffer')
    t_srs = 4326
    bins_buffer_gdf.set_geometry('buffer', crs=(u'epsg:'+str(t_srs)), inplace=True)
    
    original_litter_gdf = gpd.GeoDataFrame.from_postgis('litter', engine, geom_col='geometry')
    t_srs = 4326
    original_litter_gdf.set_geometry('geometry', crs=(u'epsg:'+str(t_srs)), inplace=True)
    
    #define the critical bins (fill in the column critical in bins table (TRUE or FALSE))
    for i, r in bins_buffer_gdf.iterrows():
        #filter litter data (for each bin record buffer select litter point included in it)
        area = bins_buffer_gdf.loc[i, 'buffer']
        filt_litter_gdf = query_by_area(area)
        #make statistic analysis on filter litter data to undestand if a bin is critical (if it is critical --> put an infographic)
        critical(filt_litter_gdf, bins_buffer_gdf.loc[i, 'bin_id'])

    litter_gdf = gpd.GeoDataFrame(columns=original_litter_gdf.columns)
    for i,r in city_boundaries.iterrows():
        area = city_boundaries.loc[i,'geometry']
        filtered_litter_gdf = query_by_area(area)
        litter_gdf = litter_gdf.append(filtered_litter_gdf, ignore_index=True)
    litter_gdf.drop_duplicates(subset='geometry', keep = 'first', ignore_index = True)
    t_srs = 4326
    litter_gdf.set_geometry('geometry', crs=(u'epsg:'+str(t_srs)), inplace=True)
    
    # Calculate x and y coordinates of litter points
    litter_gdf = litter_gdf.to_crs(epsg=3857)
    litter_gdf['x'] = litter_gdf.apply(getPointCoords, geom='geometry', coord_type='x', axis=1) 
    litter_gdf['y'] = litter_gdf.apply(getPointCoords, geom='geometry', coord_type='y', axis=1)

    # Calculate x and y coordinates of bins points
    bins_gdf = bins_gdf.to_crs(epsg=3857)
    critical_bins_gdf = bins_gdf.query("critical == True")
    non_critical_bins_gdf = bins_gdf.query("critical == False")
    
    #bins_gdf['x'] = bins_gdf.apply(getPointCoords, geom='geom', coord_type='x', axis=1) 
    #bins_gdf['y'] = bins_gdf.apply(getPointCoords, geom='geom', coord_type='y', axis=1)
    
    critical_bins_gdf['x'] = critical_bins_gdf.apply(getPointCoords, geom='geom', coord_type='x', axis=1) 
    critical_bins_gdf['y'] = critical_bins_gdf.apply(getPointCoords, geom='geom', coord_type='y', axis=1)
    
    non_critical_bins_gdf['x'] = non_critical_bins_gdf.apply(getPointCoords, geom='geom', coord_type='x', axis=1) 
    non_critical_bins_gdf['y'] = non_critical_bins_gdf.apply(getPointCoords, geom='geom', coord_type='y', axis=1)
    
    # Make a copy, drop the geometry column and create ColumnDataSource referring to litter points
    litter_df = litter_gdf.drop('geometry', axis=1).copy()
    littersource = ColumnDataSource(litter_df)
    
    #bins_df = bins_gdf.drop('geom', axis=1).copy()
    #binssource = ColumnDataSource(bins_df)
    
    critical_bins_df = critical_bins_gdf.drop('geom', axis=1).copy()
    criticalbinssource = ColumnDataSource(critical_bins_df)

    non_critical_bins_df = non_critical_bins_gdf.drop('geom', axis=1).copy()
    noncriticalbinssource = ColumnDataSource(non_critical_bins_df)

    #Map with litter
    #CREATE THE MAP PLOT
    # define range bounds supplied in web mercator coordinates epsg=3857 retrieving them from longitude and latitude
    p1 = figure(x_range=((litter_gdf.x.min()-10), (litter_gdf.x.max()+10)), y_range=((litter_gdf.y.min()-10), (litter_gdf.y.max()+10)),
           x_axis_type="mercator", y_axis_type="mercator",plot_width=700, plot_height=700,tools="pan,wheel_zoom,box_zoom,reset,save",title="Visualize clusters of litter points")
    p1.axis.visible = False
    p1.add_tile(get_provider(Vendors.OSM))

    #adding litter points
    p1.circle('x', 'y', source=littersource, size=7, color="black",legend_label='Litter')

    #ADDING TOOLTIPS TO SHOW INFORMATION ABOUT LITTER POINT
    hover = HoverTool(tooltips="""
        <div>
            <div>
                <img
                    src="@Photo" height="82" alt="@Photo" width="82"
                    style="left; margin: 10px 20px 20px 10px;"
                    border="2"
                ></img>
            </div>
            <div>
                <span style="font-size: 12px;">@Lytter_type</span>
            </div>
            <div>
                <span style="font-size: 12px;">Quantity: @Quantity</span>
            </div>
            <div>
                <span style="font-size: 12px;">Type of infrastructure: @Type_of_infrastructure</span>
            </div>
            <div>
                <span style="font-size: 12px;">Location</span>
                <span style="font-size: 10px; color: #696;">(@Longitude, @Latitude)</span>
            </div>
        </div>
    """)

    p1.add_tools(hover)

	    #Add Labels and add to the plot layout
    labels = LabelSet(x='x', y='y', text='ID', level="glyph",
              x_offset=5, y_offset=5, render_mode='css')

    p1.add_layout(labels)

    # Assign the legend to the bottom left
    p1.legend.location = 'bottom_left'

    # Fill the legend background with the color 'lightgray'
    p1.legend.background_fill_color = 'white'

	
    #CREATE THE MAP PLOT of bins
    # define range bounds supplied in web mercator coordinates epsg=3857 retrieving them from longitude and latitude

    x_min = critical_bins_gdf.x.min() 
    if x_min > non_critical_bins_gdf.x.min():
        x_min = non_critical_bins_gdf.x.min()
    x_max = critical_bins_gdf.x.max()
    if x_max < non_critical_bins_gdf.x.max():
        x_max = non_critical_bins_gdf.x.max()
    y_min = critical_bins_gdf.y.min()
    if y_min > non_critical_bins_gdf.y.min():
        y_min = non_critical_bins_gdf.y.min()
    y_max = critical_bins_gdf.y.max()
    if y_max < non_critical_bins_gdf.y.max():
        y_max = non_critical_bins_gdf.y.max()    
    
    # range bounds supplied in web mercator coordinates epsg=3857
    p2 = figure(x_range=((x_min-500), (x_max+500)), y_range=((y_min-500), (y_max+500)),
           x_axis_type="mercator", y_axis_type="mercator",plot_width=700, plot_height=700,tools="pan,wheel_zoom,box_zoom,reset,save,tap", title='Visualize statistical analysis results and update bin')
    p2.axis.visible = False

    #ADDING TAPTOOL
    
    url = 'http://127.0.0.1:5000/create_image'
    taptool = p2.select(type=TapTool)
    taptool.callback = OpenURL(url=url)

    p2.add_tile(get_provider(Vendors.OSM))

    #p2.circle('x', 'y', source=binssource, color='blue', size=7, legend_label='Bins points')   
    #p2.circle('x', 'y', source=binssource, fill_color=colors, size=7, legend_label='Bins points')    

    #add non-critical bins points(as green points) on top
    p2.circle('x', 'y', source=noncriticalbinssource, color="green", size=7, legend_label='Non-critical bins points')
    
    #add critical bins points(as red points) on top
    p2.circle('x', 'y', source=criticalbinssource, color="red", size=7, legend_label='Critical bins points')

    #ADDING TOOLTIPS TO SHOW INFORMATION ABOUT LITTER POINT
    tooltips=("""
            <div>
                <div>
                    <span style="font-size: 12px;">ID: @bin_id</span>
                </div>
                <div>
                    <span style="font-size: 12px;">Click to see if infographic is needed!</span>
                </div>
                <div>
                <span style="font-size: 12px;">Location</span>
                <span style="font-size: 10px; color: #696;">(@lon, @lat)</span>
                </div>
            </div>
            """)
    hover = HoverTool(tooltips=tooltips)
    p2.add_tools(hover)

    #Add Labels and add to the plot layout
    labels = LabelSet(x='x', y='y', text='ID', level="glyph",
              x_offset=5, y_offset=5, render_mode='css')

    p2.add_layout(labels)

    # Assign the legend to the bottom left
    p2.legend.location = 'bottom_left'

    # Fill the legend background with the color 'white'
    p2.legend.background_fill_color = 'white'

    output_file("templates/InteractiveMap.html")
    layer = row(p1,p2)
    
    return show(layer)
