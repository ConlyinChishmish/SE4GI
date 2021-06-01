#function for retrieving PA boundaries data from OSM (to be called in registration after bintable())
def boundary(locality):
    locality =  locality + ", Australia"
    tags = {"boundary": "administrative"} 
    boundaryOSM = ox.geometries_from_place(locality, tags)
    g.boundary_gdf = gpd.GeoDataFrame(boundaryOSM)
    return

from bokeh.plotting import figure, show, output_file
from bokeh.models import ColumnDataSource, HoverTool, LabelSet
from bokeh.models.tools import LassoSelectTool, TapTool
from bokeh.tile_providers import Vendors, get_provider
from bokeh.io import output_notebook, curdoc
output_notebook ()


def getPolyCoords(row, geom, coord_type):
    #returns the coordinates ('x' or 'y') of edges of a Polygon exterior

    # Parse the exterior of the coordinate
    exterior = row[geom].exterior

    if coord_type == 'x':
        # Get the x coordinates of the exterior
        return list( exterior.coords.xy[0] )
    elif coord_type == 'y':
        # Get the y coordinates of the exterior
        return list( exterior.coords.xy[1] )

  
def interactive_map():	

    #importing litter and bins data from DB
    engine = customized_engine()
    bins_gdf = gpd.GeoDataFrame.from_postgis('bins', engine, geom_col='buffer')
    litter_gdf = gpd.GeoDataFrame.from_postgis('litter', engine, geom_col='geometry')
	
    #filter litter data according to the registered PA
    cityBoundaries = boundary_gdf["geometry"][1]
    litter_gdf = queryByArea(cityBoundaries)

    #filter litter data according to a 30 days temporal window starting from last record Date_of_creation
    litter_gdf = queryByTemp()

    #define the critical bins (fill in the column critical in bins table (TRUE or FALSE))
    for i, row in bins_gdf.iterrows():
    #filter litter data (for each bin record's buffer select litter points included in it)
        area = bins_gdf.loc[i, 'Buffer'][1]
        filt_litter_gdf = queryByArea(area)
        #make statistic analysis on filtered litter data to undestand if a bin is critical (if it is critical --> put an infographic)
        id_bin = bins_gdf.loc[i, 'bin_id']
        analysis(filt_litter_gdf, id_bin)
	
    #all data must have the same crs
    litter_gdf["geometry"] = litter_gdf.to_crs(epsg=3857)
    bins_gdf["geometry"] = bins_gdf.to_crs(epsg=3857)
    bins_gdf["buffer"] = bins_gdf.to_crs(epsg=3857)  
	
    #creating two different gdf referring to critical and non-critical bins
    critical_bins = bins_gdf.query('critical == True')
    non_critical_bins = bins_gdf.query('critical == False')

    # Calculate x and y coordinates of litter points
    litter_gdf['x'] = litter_gdf.apply(getPointCoords, geom='geometry', coord_type='x', axis=1)
    litter_gdf['y'] = litter_gdf.apply(getPointCoords, geom='geometry', coord_type='y', axis=1)

    # Calculate x and y coordinates of the non-critical bins points
    non_critical_bins['x'] = non_critical_bins.apply(getPointCoords, geom='geometry', coord_type='x', axis=1)
    non_critical_bins['y'] = non_critical_bins.apply(getPointCoords, geom='geometry', coord_type='y', axis=1)
 
    # Calculate x and y coordinates of the critical bins points
    critical_bins['x'] = critical_bins.apply(getPointCoords, geom='geometry', coord_type='x', axis=1)
    critical_bins['y'] = critical_bins.apply(getPointCoords, geom='geometry', coord_type='y', axis=1)

    # Get the Polygon x and y coordinates of the bins' buffers
    bins_gdf['x'] = bins_gdf.apply(getPolyCoords, geom='buffer', coord_type='x', axis=1)
    bins_gdf['y'] = bins_gdf.apply(getPolyCoords, geom='buffer', coord_type='y', axis=1)

    # Make a copy, drop the geometry column and create ColumnDataSource referring to litter points
    litter_df = litter_gdf.drop('geometry', axis=1).copy()
    littersource = ColumnDataSource(litter_df)

    # Make a copy, drop the geometry column and create ColumnDataSource referring to non-critical bins points
    ncbins_df = non_critical_bins.drop('geometry', axis=1).copy()
    ncbinssource = ColumnDataSource(ncbins_df)

    # Make a copy, drop the geometry column and create ColumnDataSource referring to critical bins points
    cbins_df = critical_bins.drop('geometry', axis=1).copy()
    cbinssource = ColumnDataSource(cbins_df)

    # Make a copy, drop the geometry column and create ColumnDataSource referring to bins' buffers
    binsbuffer_df = bins_gdf.drop('buffer', axis=1).copy()
    binsbuffersource = ColumnDataSource(binsbuffer_df)
	
    #ADDING TOOLTIPS TO SHOW INFORMATION ABOUT LITTER POINT
    TOOLTIPS = [('Date', '@Date_of_creation'), ('Time', '@Time_of_creation'), ('Lytter type', '@Lytter_type'),('Quantity', '@Quantity'), ('Type of infrastructure', '@Type_of_infrastructure'), ('Comment', '@Comment'), ('Photo', '@Photo')]

    #CREATE THE MAP PLOT
    # Initialize our figure
    p = figure(x_axis_type="mercator",y_axis_type="mercator",tooltips=TOOLTIPS, tools="pan,wheel_zoom,box_zoom,reset,lasso_select,tap", active_drag="lasso_select")
    #add basemap tile
    p.add_tile(get_provider(Vendors.CARTODBPOSITRON))

    #add bins' buffers polygons(as brown points) 
    p.patches('x', 'y', source=binsbuffersource, fill_color= "lightgray", fill_alpha=0.3, line_color="gray", line_width=0.05, legend_label='Bins buffers (500 m)')

    #add non-critical bins points(as black points) on top
    p.circle('x', 'y', source=ncbinssource, color="black", radius=10, legend_label='Non-critical bins points')

    #add litter points(as brown x) on top
    litterpoints = p.x('x', 'y', source=littersource, color="brown", legend_label='Litter')

    #add critical bins points(as red points) on top
    criticalbinpoints = p.circle('x', 'y', source=cbinssource, color="red", legend_label='Critical bins points',selection_color="yellow")

    # Assign the legend to the bottom left
    p.legend.location = 'bottom_left'

    # Fill the legend background with the color 'lightgray'
    p.legend.background_fill_color = 'lightgray'

    output_file('interactive_map.html')
    show(p)

    #GO TO UPDATE BIN by clicking on it

    def tap_function():
        g.binpoint = source.selected.indices #I don't know what are the indices, I have to run it in jupyter to understand how to manipulate this data (we want the bin's id)
        return url_for(update_bin)
	
    taptool = p.select(type=TapTool)[3] #select only critical bin points
    taptool.renderers.append(criticalbinpoints) #or taptool.renderers= [points,]
    taptool.callback = tap_function()

    #GO TO VISUALIZE RESULTS WITH DATA SELECTED WITH LASSO SELECT TOOL 

    def lasso_function():
        g.data = source.selected.indices #I don't know what are the indices, I have to run it in jupyter to understand how to manipulate this data (we want the df of selected litter)
        analysis(data, None)
    lassoselect = p.select(type=LassoSelectTool)[2] #select only litter points
    lassoselect.renderers.append(litterpoints) #or lassoselect.renderers= [litterpoints,]
    lassoselect.callback = lasso_function()
    return
