from flask import (
    Flask, url_for
)

import geopandas as gpd

from sqlalchemy import create_engine

from bokeh.plotting import figure, show, output_file
from bokeh.models import ColumnDataSource, LabelSet, HoverTool, OpenURL, TapTool
from bokeh.models.tools import TapTool
from bokeh.tile_providers import get_provider, Vendors
from bokeh.io import output_notebook, show
from bokeh.layouts import row
output_notebook ()
    
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
    engine = customized_engine()
    # putting all the points into a geodataframe
    gdf_litt = gpd.GeoDataFrame.from_postgis('litter', engine, geom_col='geometry')
    # select the points contained in the area
    filtered_litter = gdf_litt[gdf_litt.geometry.within(area)]
    
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

def interactive_map(city_boundaries):
	
    engine = customized_engine()

    bins_gdf = gpd.GeoDataFrame.from_postgis('bins', engine, geom_col='geom')
    t_srs = 4326
    bins_gdf.set_geometry('geom', crs=(u'epsg:'+str(t_srs)), inplace=True)
    
    original_litter_gdf = gpd.GeoDataFrame.from_postgis('litter', engine, geom_col='geometry')
    t_srs = 4326
    original_litter_gdf.set_geometry('geometry', crs=(u'epsg:'+str(t_srs)), inplace=True)

    
    litter_gdf = gpd.GeoDataFrame(columns=original_litter_gdf.columns)
    for i,row in city_boundaries.iterrows():
        area = city_boundaries.loc[i,'geometry']
        filtered_litter_gdf = query_by_area(area)
        litter_gdf = litter_gdf.append(filtered_litter_gdf, ignore_index=True)
    litter_gdf.drop_duplicates(subset='geometry', keep = 'first', ignore_index = True)
    t_srs = 4326
    litter_gdf.set_geometry('geometry', crs=(u'epsg:'+str(t_srs)), inplace=True)
    
    #filter litter data according to a 30 days temporal window starting from last record Date_of_creation
    litter_gdf = query_temp()
    t_srs = 4326
    litter_gdf.set_geometry('geometry', crs=(u'epsg:'+str(t_srs)), inplace=True)

    # Calculate x and y coordinates of litter points
    litter_gdf = litter_gdf.to_crs(epsg=3857)
    litter_gdf['x'] = litter_gdf.apply(getPointCoords, geom='geometry', coord_type='x', axis=1) 
    litter_gdf['y'] = litter_gdf.apply(getPointCoords, geom='geometry', coord_type='y', axis=1)

    # Calculate x and y coordinates of bins points
    bins_gdf = bins_gdf.to_crs(epsg=3857)
    bins_gdf['x'] = bins_gdf.apply(getPointCoords, geom='geom', coord_type='x', axis=1) 
    bins_gdf['y'] = bins_gdf.apply(getPointCoords, geom='geom', coord_type='y', axis=1)
    
    # Make a copy, drop the geometry column and create ColumnDataSource referring to litter points
    litter_df = litter_gdf.drop('geometry', axis=1).copy()
    littersource = ColumnDataSource(litter_df)

    bins_df = bins_gdf.drop('geom', axis=1).copy()
    binssource = ColumnDataSource(bins_df)

    #Map with litter
    #CREATE THE MAP PLOT
    # define range bounds supplied in web mercator coordinates epsg=3857 retrieving them from longitude and latitude
    p1 = figure(x_range=((litter_gdf.x.min()-10), (litter_gdf.x.max()+10)), y_range=((litter_gdf.y.min()-10), (litter_gdf.y.max()+10)),
           x_axis_type="mercator", y_axis_type="mercator",plot_width=700, plot_height=700,tools="pan,wheel_zoom,box_zoom,reset,save",title="Visualize clusters of litter points")
    p1.axis.visible = False
    p1.add_tile(get_provider(Vendors.OSM))

    #adding litter points
    p1.circle('x', 'y', source=littersource, size=7, color="red",legend_label='Litter')

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

    # range bounds supplied in web mercator coordinates epsg=3857
    p2 = figure(x_range=((bins_gdf.x.min()-500), (bins_gdf.x.max()+500)), y_range=((bins_gdf.y.min()-500), (bins_gdf.y.max()+500)),
           x_axis_type="mercator", y_axis_type="mercator",plot_width=700, plot_height=700,tools="pan,wheel_zoom,box_zoom,reset,save,tap", title='Visualize statistical analysis results and update bin')
    p2.axis.visible = False

    #ADDING TAPTOOL
    url = url_for('visualize_results')
    taptool = p2.select(type=TapTool)
    taptool.callback = OpenURL(url=url)

    p2.add_tile(get_provider(Vendors.OSM))

    #add critical bins points(as black points) on top
    p2.circle('x', 'y', source=binssource, color="black", size=7, legend_label='Bins points')

    #ADDING TOOLTIPS TO SHOW INFORMATION ABOUT LITTER POINT
    tooltips=("""
            <div>
                <div>
                    <span style="font-size: 12px;">ID: @bin_id</span>
                </div>
                <div>
                    <span style="font-size: 12px;">Click to see if infographic is needed!</span>
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

    # Fill the legend background with the color 'lightgray'
    p2.legend.background_fill_color = 'white'

    output_file("Interactive_map.html")
    layer = row(p1,p2)
    show(layer)
    
    return 	
