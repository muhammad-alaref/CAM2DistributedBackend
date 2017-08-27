import sqlite3

class DatabaseClient(object):
	
	def __init__(self, database_path):
		self._db = sqlite3.connect(database_path, check_same_thread=False)

	def update_db(self, query, args=()):
		self._db.execute(query, args)
		self._db.commit()

	def query_db(self, query, args=(), one=False):
		cursor = self._db.execute(query, args)
		if one:
			return cursor.fetchone()
		else:
			return cursor.fetchall()
	
	def close_connection(self):
		self._db.close()
