import pandas as pd
from tqdm import tqdm
import json
from neo4j import GraphDatabase

file = "./arxiv-metadata-oai-snapshot.json"

metadata  = []

lines = 1000    # 1k for testing

with open(file, 'r') as f:

    for line in tqdm(f):
        metadata.append(json.loads(line))
        lines -= 1
        if lines == 0: break

     
df = pd.DataFrame(metadata)

# print(df['authors_parsed'].iloc[0])

# helper functions

def get_author_list(line):
    # Cleans author dataframe column, creating a list of authors in the row.
    return [e[1] + ' ' + e[0] for e in line]

def get_category_list(line):
    # Cleans category dataframe column, creating a list of categories in the row.
    return list(line.split(" "))

df['cleaned_authors_list'] = df['authors_parsed'].map(get_author_list)
# print(df['cleaned_authors_list'].info())
df['category_list'] = df['categories'].map(get_category_list)
# print(df['category_list'].iloc[1])

# we will drop all the other columns from the dataset except 
# id , title , cleaned_authors_list and category_list 

df = df.drop(['submitter', 'authors', 
             'comments', 'journal-ref', 
             'doi', 'report-no', 'license', 
             'versions', 'update_date', 
             'abstract', 'authors_parsed', 
             'categories'], axis=1)

# print(df.head(1))

# create a class for making connections

class Neo4jConnection:
    
    def __init__(self, uri, user, pwd):
        self.__uri = uri
        self.__user = user
        self.__pwd = pwd
        self.__driver = None
        try:
            self.__driver = GraphDatabase.driver(self.__uri, auth=(self.__user, self.__pwd))
        except Exception as e:
            print("Failed to create the driver:", e)
        
    def close(self):
        if self.__driver is not None:
            self.__driver.close()
        
    def query(self, query, parameters=None, db=None):
        assert self.__driver is not None, "Driver not initialized!"
        session = None
        response = None
        try: 
            session = self.__driver.session(database=db) if db is not None else self.__driver.session() 
            response = list(session.run(query, parameters))
        except Exception as e:
            print("Query failed:", e)
        finally: 
            if session is not None:
                session.close()
        return response


conn = Neo4jConnection(uri="bolt://54.165.178.82:7687", 
                       user="neo4j",              
                       pwd="bails-string-transfers")
