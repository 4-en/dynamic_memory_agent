# Neo4j implementation of GraphMemory

from neo4j import GraphDatabase
from .graph_result import GraphResult

from .graph_memory import GraphMemory
from dma.core import Memory, FeedbackType
import os


class Neo4jMemory(GraphMemory):
    def __init__(
        self,
        uri: str = "neo4j://localhost:7687",
        user: str = "neo4j",
        password: str = "testtest",
        database: str = "neo4j"
    ):
        
        # use following priority to get connection info:
        # 1. parameters if non default
        # 2. environment variables
        # 3. default values

        if uri == "neo4j://localhost:7687":
            uri = os.getenv("NEO4J_URI", uri)
        if user == "neo4j":
            user = os.getenv("NEO4J_USER", user)
        if password == "testtest":
            password = os.getenv("NEO4J_PASSWORD", password)
        if database == "neo4j":
            database = os.getenv("NEO4J_DATABASE", database)
        

        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        
        if self._is_connected():
            self._create_db_if_not_exists()
        else:
            raise ConnectionError("Could not connect to Neo4j database.")
        
    def _create_db_if_not_exists(self):
        # note: this requires the user to have admin privileges
        # and Neo4j enterprise edition
        # the community edition uses 'neo4j' as the default and only database
        with self.driver.session() as session:
            session.run(f"CREATE DATABASE {self.database} IF NOT EXISTS")

    def _is_connected(self) -> bool:
        try:
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")
            return True
        except Exception:
            return False
        
    
        
        