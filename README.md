# SE4GI- BinEco
HOW TO USE IT
1) You must have a postgreSQL-postGIS database
2) You must have an anaconda environment in which install the following libraries:
    - flask
    - geopandas
    - spyder
    - geopy descartes seaborn contextily requests folium flask bokeh git
    - jmcmurray json
    - sqlalchemy
    - geoalchemy2
    - psycopg2
    - osmnx
4) Dowload the project on your personal computer
5) Open the file dBconfig.txt in the IMPLEMENTATION folder and modify it by inserting the name of you're postgreSQL database, username and password
6) Open the anaconda terminal and activate the environment with the command: conda activate se4g
7) Navigate to the folder cd your-path\SE4GI\IMPLEMENTATION
8) Initialize the database with the command: python createSchema.py
9) Launch the program with the command: python BinEcoCode.py
10) Open the browser at http:\127.0.0.1:5000\

Thank you very much
