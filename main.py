import pandas as pd
from tqdm import tqdm
import json
from neo4j import GraphDatabase
import time

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

# query neo4j using python and populate the database

conn.query('CREATE CONSTRAINT papers IF NOT EXISTS FOR (p:Paper)  REQUIRE p.id IS UNIQUE')
conn.query('CREATE CONSTRAINT authors IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE')
conn.query('CREATE CONSTRAINT categories IF NOT EXISTS FOR (c:Category) REQUIRE c.category IS UNIQUE')


def add_categories(categories):
    # Adds category nodes to the Neo4j graph.
    query = '''
            UNWIND $rows AS row
            MERGE (c:Category {category: row.category})
            RETURN count(*) as total
            '''
    return conn.query(query, parameters = {'rows':categories.to_dict('records')})


def add_authors(rows, batch_size=100):
    # Adds author nodes to the Neo4j graph as a batch job.
    query = '''
            UNWIND $rows AS row
            MERGE (:Author {name: row.author})
            RETURN count(*) as total
            '''
    return insert_data(query, rows, batch_size)


def insert_data(query, rows, batch_size = 100):
    # Function to handle the updating the Neo4j database in batch mode.
    
    total = 0
    batch = 0
    start = time.time()
    result = None
    
    while batch * batch_size < len(rows):

        res = conn.query(query, 
                         parameters = {'rows': rows[batch*batch_size:(batch+1)*batch_size].to_dict('records')})
        total += res[0]['total']
        batch += 1
        result = {"total":total, 
                  "batches":batch, 
                  "time":time.time()-start}
        print(result)
        
    return result

# paper node 

def add_papers(rows, batch_size=5000):
   # Adds paper nodes and (:Author)--(:Paper) and 
   # (:Paper)--(:Category) relationships to the Neo4j graph as a 
   # batch job.
 
   query = '''
   UNWIND $rows as row
   MERGE (p:Paper {id:row.id}) ON CREATE SET p.title = row.title
 
   // connect categories
   WITH row, p
   UNWIND row.category_list AS category_name
   MATCH (c:Category {category: category_name})
   MERGE (p)-[:IN_CATEGORY]->(c)
 
   // connect authors
   WITH distinct row, p // reduce cardinality
   UNWIND row.cleaned_authors_list AS author
   MATCH (a:Author {name: author})
   MERGE (a)-[:AUTHORED]->(p)
   RETURN count(distinct p) as total
   '''
 
   return insert_data(query, rows, batch_size)


categories = pd.DataFrame(df[['category_list']])
categories.rename(columns={'category_list':'category'},
                  inplace=True)
categories = categories.explode('category') \
                       .drop_duplicates(subset=['category'])

authors = pd.DataFrame(df[['cleaned_authors_list']])
authors.rename(columns={'cleaned_authors_list':'author'},
               inplace=True)
authors=authors.explode('author').drop_duplicates(subset=['author'])

add_categories(categories)
add_authors(authors)
add_papers(df)