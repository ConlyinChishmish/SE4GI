# BinEco

<img src="https://user-images.githubusercontent.com/83450257/208455767-1a361898-230b-4a59-bea0-e29af749357c.jpg" width=350 height=130 align="right"/>

BinEco is part of the final **Software Engineering for Geoinformatics**, course of **Geoinformatics Engineering** held at Politecnico di Milano (2020/2021).

**Final Score**: 14/14

## Project Specification
The purpose of our project is to inform, to involve and to help communities potentially affected by environmental rubbish pollution by means of a web application for desktop and a mobile application.

Deliverables:
* [Requirement Analysis and Specification Document](https://github.com/ElisaServidio/SE4GI/blob/main/RASD/RASD%20-%20BinEco%20-%20Group2%20-%20Version%201.0(1).pdf);
* [Design Document](https://github.com/ElisaServidio/SE4GI/blob/main/SDD/SDD_BinEco_group2_version1.0.pdf);

## *Don't waste your time, keep it clean!*

*HOW TO USE IT*
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
5) Open the file dBconfig.txt in the IMPLEMENTATION folder and modify it by inserting the name of your postgreSQL database, username and password
6) Open the anaconda terminal and activate the environment with the command: conda activate se4g2021
7) Navigate to the folder cd your-path\SE4GI\IMPLEMENTATION
8) Initialize the database with the command: python createSchema.py
9) Launch the program with the command: python BinEcoCode.py
10) Open the browser at http:\127.0.0.1:5000\
