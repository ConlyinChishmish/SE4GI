#CREATE THE STRUCTURE OF THE MAIN TABLES OF THE DATABASE
# import packages
import pandas as pd
from sqlalchemy import create_engine
from psycopg2 import ( 
        connect
)
#variable list containing the structures of the database
commands = (
        #table of bins
        """ 
        CREATE TABLE bin(
                bin_id SERIAL PRIMARY KEY,
                bin_date TIMESTAMP DEFAULT NOW(),
                lat DOUBLE PRECISION NOT NULL,
                lon DOUBLE PRECISION NOT NULL,
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
        #table for the registrantion of PA
        """ 
            CREATE TABLE pa_user(
                postal_code VARCHAR(5) PRIMARY KEY,
                municipality VARCHAR(255) NOT NULL,
                password VARCHAR(255) NOT NULL  
        )
        """,
        
        )

#create the connection with the database
conn = connect("dbname=binecoDB user=postgres password=dbpw") #this line has to be customize with your credential of postgres
cur = conn.cursor()
for command in commands :
    cur.execute(command)
cur.close()
conn.commit()
conn.close()


#CREATE THE TABLE CONTAINING A LIST OF MUNICIPALITIES AND THEIR POSTAL CODE
#this table will be used to verify the correctness of the username during the registration of the PA

#setup db connection (generic connection path to be update with your credentials: 'postgresql://user:password@localhost:5432/mydatabase')
engine = create_engine('postgresql://postgres:r3df0x@localhost:5432/binecoDB') 

# creating the datafram of the municipalities 
# data obtained from http://lab.comuni-italiani.it/download/comuni.html
# !!NOTE: i'm using the municipality of italy because i can't find a list of australian city id
df_patemp = pd.read_csv("C:/Users/teari/Documents/polimi/semester_2_1/software_engineering/project/listacomuni.txt",sep=';')

#selecting only the usefull columns
df_pa = df_patemp[['Comune', 'Provincia', 'CAP']]

# write the dataframe into postgreSQL
df_pa.to_sql('pa_data', engine, if_exists = 'replace', index=False)
