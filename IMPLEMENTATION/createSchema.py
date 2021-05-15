#CREATE THE STRUCTURE OF THE MAIN TABLES OF THE DATABASE
# import packages
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
        )
        """
        )

#create the connection with the database
conn = connect("dbname=binecoDB user=postgres password=dbpw") #this line has to be customize with your credential of postgres
cur = conn.cursor()
for command in commands :
    cur.execute(command)
cur.close()
conn.commit()
conn.close()
