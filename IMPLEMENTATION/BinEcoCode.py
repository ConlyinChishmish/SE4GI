from flask import (
    Flask, render_template, request, redirect, flash, url_for, session, g
)

from werkzeug.security import check_password_hash, generate_password_hash

from werkzeug.exceptions import abort

from psycopg2 import (
        connect
)

from shapely.geometry import Point

from numpy import array

# Create the application instance
app = Flask(__name__, template_folder="templates")
# Set the secret key to some random bytes. Keep this really secret!
app.secret_key = '_5#y2L"F4Q8z\n\xec]/'

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
        
        
 #Add your function here
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
            cur.execute('SELECT postal_code FROM pa_user WHERE postal_code = %s', (postal_code,))
            if cur.fetchone() is not None:
                error = 'User {} is already registered.'.format(postal_code)
                cur.close()
            else:
                cur.execute('SELECT postal_code FROM pa_data WHERE postal_code = %s', (postal_code,))
                if cur.fetchone() is None:
                    error = 'User {} does not exist'.format(postal_code)
                    cur.close()
                #else:
                 # cur.execute('SELECT pa_data.locality FROM pa_data WHERE postal_code = %s', (postal_code,))
                  #if (cur.fetchone() != municipality):
					#error=cur.fetchone()
                    #error = '{} and {} do not correspond'.format(postal_code,municipality)
                     #cur.close()

        if error is None:
            conn = get_dbConn()
            cur = conn.cursor()
            cur.execute(
                'INSERT INTO pa_user (postal_code,municipality,password) VALUES (%s, %s, %s)',
                (postal_code,municipality, generate_password_hash(password))
            )
            cur.close()
            conn.commit()
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
    postal_code = session.get('postal_code')

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
        conn_close()
    if g.user is None:
        return False
    else: 
        return True
    
# Create a URL route in our application for "/"
@app.route('/')
@app.route('/index')
def index():
    if load_logged_in_user():
        return render_template('index.html')
    else:
        return render_template('about.html')


# UC.3 Pa enters new data about the bin
@app.route('/newBin', methods=('GET', 'POST'))
def new_bin():
    if request.method == 'POST' :
        lon = request.form['lon']
        lat = request.form['lat']
        infographic = request.form['infographic']
        
        geom = Point(lon,lat)    
        error = None
       
        # check if the data inserted are correct
        if (not lon or not lat):
            error = '*this data is required!'
        elif (float(lat)<-90 or float(lat)>90):
            error ='Please insert a valid value for the latitude -90<= lat <=90'
        elif(float(lon)<0 or float(lon)>=360):
            error ='Please insert a valid value for the longitude 0<= lon <360'
         
        #check if something went wrong in compiling the form  
        if error is not None :
            flash(error)
            return redirect(url_for('new_bin'))
        #everything in the form is ok, database connection is allowed
        else : 
            conn = get_dbConn()
            cur = conn.cursor()
            cur.execute('INSERT INTO bin (lon, lat, infographic, geom ) VALUES (%f, %f, %s, ST_Point(%(geom)s))', 
                        (lon, lat, infographic, geom)
                        )
            cur.close()
            conn.commit()
            return redirect(url_for('index'))
    else :
        return render_template('blog/newBin.html')       
        
g.threshold = array([0.6,0.5,0.3,0.2]) #threshold for low-medium-high-none 
#for none, if none absolute frequency overcomes the threshold (>=0.2) is not necessary to put a bin/infographic
#for low-medium-high if frequencies overcome the corresponding thresholds a bin/infographic has to be put 


def analysis(area,id_bin):
	data_geodf = queryByArea(area) #geodataframe with litter data contained in the selected area (or buffer)
	#change quantity into numeric values to compute daily mean
	for i, row in data_geodf.iterrows():
    		if data_geodf.loc[i, 'Quantity'] == "low":
        		data_geodf.loc[i, 'Quantity'] = "1"
		elif data_geodf.loc[i, 'Quantity'] == "medium":
        		data_geodf.loc[i, 'Quantity'] = "2"
		elif data_geodf.loc[i, 'Quantity'] == "high":
        		data_geodf.loc[i, 'Quantity'] = "3"
	data_geodf['Quantity'] = pd.to_numeric(data_geodf['Quantity'])
	#create a new dataframe with data grouped by date of creation and compute the mean according to the Quantity attribute
	#we obtain a dataframe with two columns, one for Date_of_creation and one for quantity's mean, each row corresponds to a certain Date_of_creation
	daily_df = data_geodf.groupby(['Date_of_creation'])['Quantity'].mean().reset_index(name='Quantity_daily_mean')
	#assign string type values "low"-"medium"-"high" to daily_df quantity means
	for i, row in daily_df.iterrows():
		if daily_df.loc[i, 'Quantity_daily_mean'] <= 1.5:
        		daily_df.loc[i, 'Quantity_daily_mean'] = "low"
		elif daily_df.loc[i, 'Quantity_daily_mean'] >= 1.5 and daily_df.loc[i, 'Quantity_daily_mean'] <= 2.5:
			daily_df.loc[i, 'Quantity_daily_mean'] = "medium"
		elif daily_df.loc[i, 'Quantity_daily_mean'] >= 2.5:
			daily_df.loc[i, 'Quantity_daily_mean'] = "high"
	#compute absolute frequences of the various quantity over 30 days (sum of each type of quantity / 30 days)
	#first count the amount of low-medium-high quantity
	frequency_df = daily_df.groupby(['Quantity_daily_mean'])['Quantity_daily_mean'].count().reset_index(name='Count')
	#then calculate absolute frequency
	for i, row in frequency_df.iterrows():
		frequency_df.loc[i, 'Absolute_frequency'] = frequency_df.loc[i, 'Count']/30
	#compute none frequency
	none_quantity = 'none'
	none_count = 30-(frequency_df['Count'].sum())
	none_frequency = 1-(frequency_df['Absolute_frequency'].sum())

	frequency_df.loc[frequency_df.index.max()+1] = [none_quantity, none_count, none_frequency]
	#order rows according to quantity
	frequency_df['Quantity_daily_mean'] = pd.Categorical(frequency_df['Quantity_daily_mean'],categories=['low','medium','high','none'])
	frequency_df = frequency_df.sort_values('Quantity_daily_mean', ignore_index=True)
	
	#if bin is not contained in the area return array of absolute frequencies
	absolute_frequency_array = frequency_df['Absolute_frequency'].to_numpy()
	if id_bin is None:
		return absolute_frequency_array
	#if bin is contained in the area return boolean variable newItem (if TRUE --> put infographic)
	else:
		if absolute_frequency_array[0] >= 0.7:
    			newItem = False
		elif absolute_frequency_array[0] <= 0.2:
    			newItem = True
		elif absolute_frequency_array[1] >= 0.6:
    			newItem = True
		elif absolute_frequency_array[2] >= 0.5:
    			newItem = True
		elif absolute_frequency_array[3] >= 0.3:
    			newItem = True
		return newItem

@app.route('/create_comment', methods=('GET', 'POST'))
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
                return redirect(url_for('create_comment'))
            else : 
                conn = get_dbConn()
                cur = conn.cursor()
                cur.execute('INSERT INTO post (title, body, author_id) VALUES (%s, %s, %s)', 
                            (title, body, g.user[0])
                            )
                cur.close()
                conn.commit()
                return redirect(url_for('index'))
        else :
            return render_template('blog/createComment.html')
    else :
        error = 'Only loggedin users can insert comments!'
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

@app.route('/<int:id>/update_comment', methods=('GET', 'POST'))
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
                return redirect(url_for('update_comment'))
            else : 
                conn = get_dbConn()
                cur = conn.cursor()
                cur.execute('UPDATE comment SET title = %s, body = %s'
                               'WHERE comment_id = %s', 
                               (title, body, id)
                               )
                cur.close()
                conn.commit()
                return redirect(url_for('index'))
        else :
            return render_template('blog/updateComment.html', comment = comment)
    else :
        error = 'Only loggedin users can insert comments!'
        flash(error)
        return redirect(url_for('login'))

@app.route('/<int:id>/delete_comment', methods=('POST',))
def delete_comment(id):
    conn = get_dbConn()                
    cur = conn.cursor()
    cur.execute('DELETE FROM comments WHERE comment_id = %s', (id,))
    conn.commit()
    return redirect(url_for('index'))        
        
        
if __name__ == '__main__':
	app.run(debug=True)
